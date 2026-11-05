"""
Unit tests for agent/refund_logic.py: the deterministic ownership and
threshold checks Design Note 17 built, checked here with no framework, no
model, and no real AWS calls involved, exactly the "unit test" category
Design Note 26 distinguished from agent behavior evaluation.

Run:

    python3 -m pytest tests/test_refund_logic.py -v
"""

import sys
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "agent"))

import refund_logic  # noqa: E402


@pytest.fixture(autouse=True)
def mock_tables():
    """Replace refund_logic's module-level DynamoDB tables with mocks.

    No real AWS account or credentials needed to run this suite; that's
    the point of a unit test as Design Note 26 defined it.
    """
    with patch.object(refund_logic, "orders_table") as mock_orders, patch.object(
        refund_logic, "approvals_table"
    ) as mock_approvals, patch.object(
        refund_logic, "idempotency_table"
    ) as mock_idempotency, patch.object(refund_logic, "emit_metric"):
        mock_idempotency.get_item.return_value = {}  # no prior record, by default
        yield mock_orders, mock_approvals, mock_idempotency


def test_denies_refund_for_order_that_does_not_exist(mock_tables):
    mock_orders, _, _ = mock_tables
    mock_orders.get_item.return_value = {}

    result = refund_logic.request_refund(
        actor_id="CUST-4471", order_id="FB-99999", amount=50, reason="test"
    )

    assert result["status"] == "denied"
    assert "No order found" in result["reason"]


def test_denies_refund_for_order_belonging_to_a_different_customer(mock_tables):
    mock_orders, _, _ = mock_tables
    mock_orders.get_item.return_value = {
        "Item": {"order_id": "FB-10402", "customer_id": "CUST-5502"}
    }

    result = refund_logic.request_refund(
        actor_id="CUST-4471", order_id="FB-10402", amount=50, reason="test"
    )

    assert result["status"] == "denied"
    # The denial must never reveal who the order actually belongs to.
    assert "CUST-5502" not in str(result)


def test_approves_refund_at_or_under_threshold_automatically(mock_tables):
    mock_orders, _, _ = mock_tables
    mock_orders.get_item.return_value = {
        "Item": {"order_id": "FB-10293", "customer_id": "CUST-4471"}
    }

    result = refund_logic.request_refund(
        actor_id="CUST-4471",
        order_id="FB-10293",
        amount=refund_logic.AUTO_APPROVAL_THRESHOLD_USD,
        reason="damaged item",
    )

    assert result["status"] == "approved"
    assert result["approval"] == "automatic"
    mock_orders.update_item.assert_called_once()


def test_queues_refund_above_threshold_for_human_review(mock_tables):
    mock_orders, mock_approvals, _ = mock_tables
    mock_orders.get_item.return_value = {
        "Item": {"order_id": "FB-10293", "customer_id": "CUST-4471"}
    }

    result = refund_logic.request_refund(
        actor_id="CUST-4471",
        order_id="FB-10293",
        amount=refund_logic.AUTO_APPROVAL_THRESHOLD_USD + 0.01,
        reason="damaged item",
    )

    assert result["status"] == "pending_approval"
    mock_approvals.put_item.assert_called_once()
    # An amount one cent over the threshold must not be auto-approved;
    # this is the exact boundary a prompt-injection attempt (Design Note 26)
    # would try to talk the agent past.
    mock_orders.update_item.assert_not_called()


def test_repeated_identical_request_is_not_processed_twice(mock_tables):
    """The idempotency check this design note adds: calling request_refund
    twice with identical arguments must not update the order a second
    time, the exact duplicate-refund risk named all the way back in
    Design Note 17 and left open until now.
    """
    mock_orders, _, mock_idempotency = mock_tables
    mock_orders.get_item.return_value = {
        "Item": {"order_id": "FB-10293", "customer_id": "CUST-4471"}
    }

    args = dict(
        actor_id="CUST-4471", order_id="FB-10293", amount=50, reason="damaged item"
    )

    first_result = refund_logic.request_refund(**args)
    assert first_result["status"] == "approved"
    assert mock_orders.update_item.call_count == 1

    # Simulate the second call seeing the record the first call wrote.
    stored_item = mock_idempotency.put_item.call_args.kwargs["Item"]
    mock_idempotency.get_item.return_value = {"Item": stored_item}

    second_result = refund_logic.request_refund(**args)

    assert second_result == first_result
    # The critical assertion: the order was only ever updated once,
    # even though request_refund() was called twice with identical
    # arguments.
    assert mock_orders.update_item.call_count == 1

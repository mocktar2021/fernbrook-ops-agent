"""
Minimal helper for emitting custom CloudWatch metrics using Embedded
Metric Format (EMF): a specially structured log line that CloudWatch
automatically parses into a real, graphable metric, with no separate
PutMetricData API call, and no new IAM permission, since it's ordinary
log output, using whatever logging permission the process already has.

Lives in agent/, next to the code that actually emits events, rather
than in observability/, which holds the dashboard and setup docs that
consume what this module produces. See observability/README.md for how
the two fit together.

This project uses it for exactly two signals AgentCore's own built-in
tracing doesn't surface as a running count on its own: how often a
refund gets escalated to a human, and how often the ownership check
Design Note 23 added actually denies a request. Both are business and
security signals, not infrastructure health signals, which is exactly
the kind of thing Design Note 25 argues a dashboard needs and a generic
"is the service up" view never surfaces.
"""

import json
import time


def emit_metric(
    metric_name: str,
    value: float = 1,
    unit: str = "Count",
    dimensions: dict | None = None,
) -> None:
    """Emit one EMF-formatted metric data point to stdout.

    In a Lambda function or an AgentCore Runtime process, stdout is
    already captured to CloudWatch Logs; nothing extra needs to be
    configured for this to show up as a real metric, as long as the
    log group has EMF processing enabled, which is the default.
    """
    dimensions = dimensions or {}
    document = {
        "_aws": {
            "Timestamp": int(time.time() * 1000),
            "CloudWatchMetrics": [
                {
                    "Namespace": "FernbrookOpsAgent",
                    "Dimensions": [list(dimensions.keys())] if dimensions else [[]],
                    "Metrics": [{"Name": metric_name, "Unit": unit}],
                }
            ],
        },
        metric_name: value,
        **dimensions,
    }
    print(json.dumps(document))

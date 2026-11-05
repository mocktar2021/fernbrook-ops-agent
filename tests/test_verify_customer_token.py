"""
Unit tests for identity/verify_customer_token.py: the cryptographic
verification Design Note 15 built to replace a trusted actor_id with a
verified one.

These tests generate a real RSA keypair and sign a real JWT with it, no
mocked cryptography, only the network call to Cognito's JWKS endpoint
is replaced, with a JWKS response built from the same keypair used to
sign the test tokens. That keeps this a true unit test (no AWS account,
no network access needed to run it) while still exercising the actual
signature, issuer, audience, and claim checks the real function
performs, not a stubbed-out approximation of them.

Run:

    python3 -m pytest tests/test_verify_customer_token.py -v
"""

import sys
import time
from pathlib import Path
from unittest.mock import patch

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from jose import jwk, jwt

sys.path.insert(0, str(Path(__file__).parent.parent / "identity"))

import verify_customer_token as vct  # noqa: E402

USER_POOL_ID = "us-east-1_TESTPOOL"
APP_CLIENT_ID = "test-client-id"
ISSUER = f"https://cognito-idp.us-east-1.amazonaws.com/{USER_POOL_ID}"
KEY_ID = "test-key-1"


@pytest.fixture(scope="module")
def keypair():
    """One real RSA keypair, reused across every test in this file."""
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    private_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode()
    public_pem = private_key.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    ).decode()

    public_jwk = jwk.construct(public_pem, algorithm="RS256").to_dict()
    public_jwk["kid"] = KEY_ID
    public_jwk["use"] = "sig"

    return {"private_pem": private_pem, "jwks": {"keys": [public_jwk]}}


@pytest.fixture(autouse=True)
def mock_jwks(keypair):
    """Replace the real network call to Cognito with our test JWKS."""
    with patch.object(vct, "_get_jwks", return_value=keypair["jwks"]):
        yield


def _make_token(keypair, **claim_overrides):
    now = int(time.time())
    claims = {
        "sub": "cognito-subject-abc123",
        "iss": ISSUER,
        "aud": APP_CLIENT_ID,
        "token_use": "id",
        "custom:customer_id": "CUST-4471",
        "iat": now,
        "exp": now + 3600,
    }
    claims.update(claim_overrides)
    return jwt.encode(
        claims, keypair["private_pem"], algorithm="RS256", headers={"kid": KEY_ID}
    )


def test_valid_token_returns_verified_customer_id(keypair):
    token = _make_token(keypair)
    customer_id = vct.verify_customer_token(token, USER_POOL_ID, APP_CLIENT_ID)
    assert customer_id == "CUST-4471"


def test_empty_token_is_rejected():
    with pytest.raises(ValueError, match="No customer token"):
        vct.verify_customer_token("", USER_POOL_ID, APP_CLIENT_ID)


def test_wrong_audience_is_rejected(keypair):
    token = _make_token(keypair, aud="a-different-app-client")
    with pytest.raises(Exception):
        vct.verify_customer_token(token, USER_POOL_ID, APP_CLIENT_ID)


def test_wrong_issuer_is_rejected(keypair):
    token = _make_token(
        keypair, iss="https://cognito-idp.us-east-1.amazonaws.com/us-east-1_WRONGPOOL"
    )
    with pytest.raises(Exception):
        vct.verify_customer_token(token, USER_POOL_ID, APP_CLIENT_ID)


def test_access_token_is_rejected_not_just_id_token(keypair):
    """A real distinction Design Note 15's code makes: an access token, even
    if validly signed by the same pool, is not a substitute for an ID
    token, which is where the customer_id claim actually lives.
    """
    token = _make_token(keypair, token_use="access")
    with pytest.raises(ValueError, match="Expected a Cognito ID token"):
        vct.verify_customer_token(token, USER_POOL_ID, APP_CLIENT_ID)


def test_missing_customer_id_claim_is_rejected(keypair):
    now = int(time.time())
    claims = {
        "sub": "cognito-subject-abc123",
        "iss": ISSUER,
        "aud": APP_CLIENT_ID,
        "token_use": "id",
        "iat": now,
        "exp": now + 3600,
    }
    token = jwt.encode(
        claims, keypair["private_pem"], algorithm="RS256", headers={"kid": KEY_ID}
    )
    with pytest.raises(ValueError, match="no customer_id claim"):
        vct.verify_customer_token(token, USER_POOL_ID, APP_CLIENT_ID)


def test_expired_token_is_rejected(keypair):
    now = int(time.time())
    token = _make_token(keypair, iat=now - 7200, exp=now - 3600)
    with pytest.raises(Exception):
        vct.verify_customer_token(token, USER_POOL_ID, APP_CLIENT_ID)


def test_token_signed_by_unrecognized_key_is_rejected(keypair):
    """A token signed with a completely different keypair, one whose
    public half was never published in our (mocked) JWKS response,
    must be rejected. This is the actual signature check, not just the
    claims check, and it's the specific property that makes this
    verification cryptographic rather than a plain string comparison.
    """
    other_private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    other_private_pem = other_private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode()

    now = int(time.time())
    claims = {
        "sub": "attacker",
        "iss": ISSUER,
        "aud": APP_CLIENT_ID,
        "token_use": "id",
        "custom:customer_id": "CUST-9999",
        "iat": now,
        "exp": now + 3600,
    }
    # Deliberately reuses the same kid, pretending to be our trusted key.
    forged_token = jwt.encode(
        claims, other_private_pem, algorithm="RS256", headers={"kid": KEY_ID}
    )

    with pytest.raises(Exception):
        vct.verify_customer_token(forged_token, USER_POOL_ID, APP_CLIENT_ID)


def test_malformed_token_is_a_value_error_not_a_library_exception():
    """app.py only catches ValueError. A garbage token must surface as one,
    or the Runtime returns a 500 instead of a clean 'could not verify'."""
    with patch.object(vct, "_get_jwks", return_value={"keys": []}):
        with pytest.raises(ValueError, match="malformed, expired, or not valid"):
            vct.verify_customer_token("not-a-real-token", USER_POOL_ID, APP_CLIENT_ID)

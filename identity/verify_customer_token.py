"""
Verifies a Cognito-issued customer ID token and returns Fernbrook's own
internal customer ID from it, cryptographically checked, not merely
asserted the way actor_id was accepted at face value from Design Note 9
through Design Note 13.

This replaces a trusted string with a verified one. It does not, on
its own, implement full production-grade token handling (JWKS caching,
key rotation, revocation checks); see the note at the bottom of this
file for what a production version would add.
"""

import json
import urllib.request

from jose import jwt
from jose.exceptions import JOSEError

REGION = "us-east-1"


def _get_jwks(user_pool_id: str) -> dict:
    url = (
        f"https://cognito-idp.{REGION}.amazonaws.com/"
        f"{user_pool_id}/.well-known/jwks.json"
    )
    with urllib.request.urlopen(url) as response:
        return json.loads(response.read())


def verify_customer_token(token: str, user_pool_id: str, app_client_id: str) -> str:
    """Verify a Cognito ID token and return the verified customer_id.

    Raises ValueError if the token is missing, expired, malformed, not
    an ID token, or not signed by Fernbrook's own customer user pool.
    Never returns a value the caller merely claimed; every value
    returned here has passed signature, issuer, and audience checks.
    """
    if not token:
        raise ValueError("No customer token was provided.")

    jwks = _get_jwks(user_pool_id)
    # python-jose raises its own JOSEError family (JWTError, ExpiredSignatureError,
    # JWTClaimsError...) for malformed, expired or mismatched tokens. Callers
    # (app.py) handle ValueError, so translate: otherwise a garbage token
    # becomes an unhandled exception and a 500 instead of a clean rejection.
    try:
        header = jwt.get_unverified_header(token)
        key = next((k for k in jwks["keys"] if k["kid"] == header.get("kid")), None)
        if key is None:
            raise ValueError("Token was not signed by a recognized key.")

        issuer = f"https://cognito-idp.{REGION}.amazonaws.com/{user_pool_id}"
        claims = jwt.decode(
            token,
            key,
            algorithms=["RS256"],
            audience=app_client_id,
            issuer=issuer,
        )
    except JOSEError as error:
        raise ValueError("Token is malformed, expired, or not valid for this app.") from error

    if claims.get("token_use") != "id":
        raise ValueError("Expected a Cognito ID token, not an access token.")

    customer_id = claims.get("custom:customer_id")
    if not customer_id:
        raise ValueError("Token has no customer_id claim.")

    return customer_id


# Production note: this function fetches the identity provider's public
# keys on every single call. A real deployment should cache the JWKS
# response (keys rotate infrequently) and refresh it on a schedule or
# when a kid it hasn't seen before shows up, rather than making a
# network call to Cognito on every request this agent handles.

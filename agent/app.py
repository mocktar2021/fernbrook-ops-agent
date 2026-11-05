"""
Wraps the Fernbrook Ops Agent (agent.py) in AgentCore Runtime's HTTP
entrypoint contract, using the bedrock_agentcore SDK. This is the file
AgentCore Runtime actually runs.

Since Design Note 15, this file no longer trusts a caller-supplied
actor_id. It requires a real Cognito customer_token instead, verifies
it, and uses the verified claim as the actor_id. A caller can no longer
simply assert who a conversation is about.
"""

import os

from bedrock_agentcore import BedrockAgentCoreApp

from agent import run_agent
from identity.verify_customer_token import verify_customer_token

USER_POOL_ID = os.environ["FERNBROOK_USER_POOL_ID"]
APP_CLIENT_ID = os.environ["FERNBROOK_APP_CLIENT_ID"]

app = BedrockAgentCoreApp()


@app.entrypoint
def invoke(payload: dict) -> dict:
    raise RuntimeError("rollback demo")
    """Handle one invocation of the deployed agent.

    Requires "prompt", "customer_token" (a Cognito ID token), and
    "session_id". actor_id is no longer read from the payload directly;
    it's derived from the verified token, so a caller can no longer
    simply claim to be a customer they haven't authenticated as.
    """
    user_message = payload.get("prompt", "")
    customer_token = payload.get("customer_token")
    session_id = payload.get("session_id")

    if not user_message:
        return {"result": "No prompt provided."}
    if not session_id:
        return {"result": "session_id is required."}

    try:
        actor_id = verify_customer_token(
            customer_token, USER_POOL_ID, APP_CLIENT_ID
        )
    except ValueError as error:
        return {"result": f"Could not verify customer identity: {error}"}

    reply = run_agent(actor_id=actor_id, session_id=session_id, prompt=user_message)
    return {"result": reply}


if __name__ == "__main__":
    app.run()

"""
The simplest possible working call to a foundation model on Amazon Bedrock,
using the Converse API. This script exists to verify your environment end
to end, before Design Note 6 introduces the Strands framework and the first
real agent loop. It is deliberately not an agent: one request, one
response, no tools, no memory, no reasoning loop.
"""

import boto3
from botocore.exceptions import ClientError

REGION = "us-east-1"

# Check the current Bedrock model catalog (console: Bedrock > Model catalog,
# or `aws bedrock list-foundation-models`) before you run this. Bedrock's
# Claude lineup has moved forward since this project was written, and a newer
# Sonnet or Opus model may be a better default by the time you read this.
MODEL_ID = "us.anthropic.claude-sonnet-5-5"


def call_model(prompt: str) -> str:
    """Send one prompt to the model and return its text response."""
    client = boto3.client("bedrock-runtime", region_name=REGION)

    try:
        response = client.converse(
            modelId=MODEL_ID,
            messages=[
                {
                    "role": "user",
                    "content": [{"text": prompt}],
                }
            ],
            # Claude Sonnet 5 and later reject temperature/top_p/top_k.
            inferenceConfig={"maxTokens": 512},
        )
    except ClientError as error:
        code = error.response["Error"]["Code"]
        if code == "AccessDeniedException":
            raise RuntimeError(
                "Access denied. Check that: (1) you've requested access to "
                f"this model in the Bedrock console for {REGION}, and "
                "(2) your IAM policy's Resource ARNs match MODEL_ID exactly, "
                "including the inference-profile ARN if you're using a "
                "cross-region profile ID (one that starts with 'us.')."
            ) from error
        if code == "ValidationException":
            raise RuntimeError(
                "The request was rejected as invalid. Check MODEL_ID is "
                "spelled correctly and is available in this region."
            ) from error
        raise

    # The first content block is not always text: newer models can return a
    # reasoning block before it. Collect every text block instead.
    blocks = response["output"]["message"]["content"]
    text = "".join(block["text"] for block in blocks if "text" in block)
    if not text:
        raise RuntimeError("The model response contained no text block.")
    return text


if __name__ == "__main__":
    answer = call_model(
        "In one short paragraph, explain what a foundation model is to "
        "someone who has never used one."
    )
    print(answer)

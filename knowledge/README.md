> **Note: not deployed by the pipelines yet (milestone 2).** The Knowledge Base and S3 Vectors store are not in the Terraform stacks. The agent treats this capability as unavailable and says so. The code and notes here are kept for when it is added.

# Fernbrook Knowledge Base

Policy and product knowledge, retrieved, not memorized. Design Note 19 covers the reasoning; this file covers the steps.

## 1. Upload the source documents

```bash
aws s3 mb s3://fernbrook-knowledge-source-<YOUR_ACCOUNT_ID>
aws s3 sync knowledge/policies/ s3://fernbrook-knowledge-source-<YOUR_ACCOUNT_ID>/policies/
```

## 2. Create the vector store (Amazon S3 Vectors)

S3 Vectors, not OpenSearch Serverless, is this project's vector store. OpenSearch Serverless is the more established option and the one most tutorials still default to, but it carries a real minimum cost, commonly several hundred dollars a month regardless of how little data it holds, because of how its capacity units are allocated. S3 Vectors is dramatically cheaper for a knowledge base this size and is a fully supported Bedrock Knowledge Bases vector store option as of this project's research; check its current status before you build, since it's newer than OpenSearch Serverless as an option here.

```bash
aws s3vectors create-vector-bucket --vector-bucket-name fernbrook-kb-vectors
aws s3vectors create-index \
  --vector-bucket-name fernbrook-kb-vectors \
  --index-name fernbrook-policy-index \
  --data-type float32 \
  --dimension 1024 \
  --distance-metric cosine
```

`1024` matches Amazon Titan Text Embeddings V2's default output size, the embedding model this project uses.

## 3. Create the Knowledge Base service role

The Knowledge Base needs its own IAM role, separate from every identity this project has created so far: it reads from the source S3 bucket, calls the embedding model, and reads and writes the S3 Vectors index. Create it with a trust policy allowing `bedrock.amazonaws.com` to assume it, and attach permissions scoped to exactly the source bucket, the embedding model, and the vector index, the same discipline every other role in this project has followed since Design Note 4.

## 4. Create the Knowledge Base and data source

```bash
aws bedrock-agent create-knowledge-base \
  --name "fernbrook-policy-knowledge-base" \
  --role-arn "arn:aws:iam::<YOUR_ACCOUNT_ID>:role/fernbrook-kb-service-role" \
  --knowledge-base-configuration '{
    "type": "VECTOR",
    "vectorKnowledgeBaseConfiguration": {
      "embeddingModelArn": "arn:aws:bedrock:us-east-1::foundation-model/amazon.titan-embed-text-v2:0",
      "embeddingModelConfiguration": {
        "bedrockEmbeddingModelConfiguration": { "dimensions": 1024, "embeddingDataType": "FLOAT32" }
      }
    }
  }' \
  --storage-configuration '{
    "type": "S3_VECTORS",
    "s3VectorsConfiguration": {
      "vectorBucketArn": "arn:aws:s3vectors:us-east-1:<YOUR_ACCOUNT_ID>:bucket/fernbrook-kb-vectors",
      "indexArn": "arn:aws:s3vectors:us-east-1:<YOUR_ACCOUNT_ID>:bucket/fernbrook-kb-vectors/index/fernbrook-policy-index"
    }
  }'
```

Note the returned `knowledgeBaseId`, then create the S3 data source pointing at the bucket from Step 1:

```bash
aws bedrock-agent create-data-source \
  --knowledge-base-id <KNOWLEDGE_BASE_ID> \
  --name "fernbrook-policy-documents" \
  --data-source-configuration '{
    "type": "S3",
    "s3Configuration": { "bucketArn": "arn:aws:s3:::fernbrook-knowledge-source-<YOUR_ACCOUNT_ID>" }
  }'
```

## 5. Ingest the documents

```bash
aws bedrock-agent start-ingestion-job \
  --knowledge-base-id <KNOWLEDGE_BASE_ID> \
  --data-source-id <DATA_SOURCE_ID>
```

This is where chunking and embedding actually happen: Bedrock splits each document into passages, generates a vector for each passage using Titan Text Embeddings V2, and writes the result into the S3 Vectors index. Re-run this command whenever the source documents change; it's how the knowledge base stays current without a code deployment, exactly the property Design Note 18 argued retrieval needed to have.

## 6. Register the Knowledge Base as a Gateway target

```bash
agentcore add gateway-target \
  --name PolicyKnowledge \
  --type knowledge-base \
  --knowledge-base-id <KNOWLEDGE_BASE_ID> \
  --gateway FernbrookGateway
agentcore deploy
```

This exposes two tools through the same Gateway the order and wholesale lookups already use: a single-search retrieval tool and a multi-step agentic retrieval tool. No new agent code, no new authentication path; this is the same chokepoint Design Notes 10 and 11 argued for, now carrying a third kind of capability.

*Note: a final repository completion pass, after Design Note 33, added graceful-degradation wrapping around this tool in `agent.py` (previously only the two lookup tools had it). That's an unrelated reliability fix, not a change to anything described in this file; registering the Knowledge Base as a Gateway target still requires none of the steps above to change.*

## 7. Update the Cedar policy

`policy/fernbrook-tool-access.cedar` needs the new action added to its permit list. See Design Note 19 for the updated policy.

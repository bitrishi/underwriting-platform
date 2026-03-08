# AI Underwriting Agent Platform

Production-grade multi-agent underwriting system built on AWS Bedrock.

## Architecture

- **Orchestrator Agent** — Routes to specialized sub-agents
- **FetchData Agent** — Pulls borrower, credit, employment data
- **Document Review Agent** — Multi-modal document analysis
- **Risk Scoring Agent** — Credit risk and DTI calculation
- **Compliance Agent** — Regulatory validation

## Tech Stack

- Python 3.11+
- AWS Bedrock (Claude) for LLM
- LangChain + LangGraph for agent orchestration
- FAISS (dev) / OpenSearch Serverless (prod) for vector search
- Neo4j for knowledge graph
- FastAPI for API layer

## Setup
```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env  # add your AWS credentials
```

## Project Structure
```
src/
├── agents/          # Agent definitions (orchestrator + sub-agents)
├── tools/           # Tool functions agents can call
├── models/          # Pydantic data models (DTOs)
├── config/          # Settings, Bedrock client setup
└── prompts/         # System prompts for each agent
tests/               # pytest test files
data/                # Documents for RAG (policies, regulations)
docs/sessions/       # Learning session notes
```
```

**`requirements.txt`** — start minimal, we'll add as we go:
```
# Core
python-dotenv==1.0.1

# We'll add these in later sessions:
# boto3
# langchain
# langchain-aws
# langgraph
# faiss-cpu
# fastapi
# uvicorn
# pydantic
```

**`.env.example`** — template for environment variables:
```
# AWS Configuration
AWS_REGION=us-east-1
AWS_PROFILE=default

# Bedrock
BEDROCK_MODEL_ID=anthropic.claude-3-sonnet-20240229-v1:0

# Application
LOG_LEVEL=INFO
ENVIRONMENT=development
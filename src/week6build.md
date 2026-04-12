# Week 6 Weekend Build: Final Integration & Deployment

**Date:** April 5, 2026  
**Module:** Final Integration  
**Platform:** Kuber Loan Origination System  

---

## 1. What You Are Building

The culmination of six weeks. Every component built across Weeks 1–6 comes together into a single deployable system. The weekend build connects:

- LangGraph orchestrator (Weeks 4–5) wrapped by FastAPI (Week 6 Day 4)
- Fronted by Streamlit dashboard (Week 6 Day 5)
- Evaluated by Ragas/Bedrock Eval (Week 6 Days 1–2)
- Optimized with prompt caching and extended thinking (Week 6 Day 3)
- Containerized with Docker Compose for local development
- Deployable to ECS Fargate for production

### 1.1 Six-Week Component Map

| Week | What You Built | Production Value |
|------|---------------|-----------------|
| **Week 1** | Python + Bedrock + Pydantic + Prompts | Foundation for every agent |
| **Week 2** | LangChain + Tools + RAG | FetchData agent with data retrieval |
| **Week 3** | Agentic RAG + Vision + Knowledge Graph | DocReview + RiskScoring agents |
| **Week 4** | LangGraph + Parallel + Routing + HITL | Compliance agent + Complete orchestrator |
| **Week 5** | MCP + A2A + Guardrails + Textract + Resilience | Production-hardened pipeline |
| **Week 6** | LangSmith + Ragas + FastAPI + Streamlit | Evaluated, deployed, usable system |

---

## 2. The Complete System Architecture

```
┌────────────────────────────────────────────────────────────────┐
│                    KUBER AI UNDERWRITING SYSTEM               │
│                                                                │
│  WEEK 6 DAY 5                    WEEK 6 DAY 4                  │
│  ┌──────────────┐               ┌──────────────────┐           │
│  │ Streamlit UI │──── HTTP ───▶│  FastAPI Server   │           │
│  │ :8501        │              │  :8000            │           │
│  │ • Submit     │              │  /evaluate /status│           │
│  │ • Monitor    │              │  /result /health  │           │
│  │ • Review     │              │                   │           │
│  └──────────────┘               └────────┬─────────┘           │
│                                          │                     │
│  WEEKS 4-5                               │                     │
│  ┌───────────────────────────────────────▼───────────────┐     │
│  │              LangGraph Orchestrator                    │     │
│  │                                                        │     │
│  │  ┌──────────┐  ┌──────────┐                            │     │
│  │  │FetchData │  │DocReview │  ← PARALLEL                │     │
│  │  │(Haiku)   │  │(Sonnet)  │                            │     │
│  │  └────┬─────┘  └────┬─────┘                            │     │
│  │       └──────┬───────┘                                 │     │
│  │              ▼                                         │     │
│  │       ┌──────────┐                                     │     │
│  │       │RiskScore │  ← Sequential                       │     │
│  │       │(Haiku)   │                                     │     │
│  │       └────┬─────┘                                     │     │
│  │            ▼                                           │     │
│  │       ┌──────────┐     ┌──────────────┐                │     │
│  │       │Compliance│────▶│Human Review  │ ← Conditional  │     │
│  │       │(Sonnet)  │     │(Interrupt)   │                │     │
│  │       └──────────┘     └──────────────┘                │     │
│  │                                                        │     │
│  │  Production Hardening (Week 5):                        │     │
│  │  • Bedrock Guardrails  • Textract hybrid               │     │
│  │  • Retry + circuit breaker  • Graceful degradation     │     │
│  └────────────────────────────────────────────────────────┘     │
│                                                                │
│  Foundation: Bedrock + Redis + OpenSearch + Neo4j              │
│  Observability: Langfuse + Bedrock Eval + DeepEval CI          │
└────────────────────────────────────────────────────────────────┘
```

---

## 3. Docker Compose — Local Development Stack

```yaml
version: "3.9"

services:
  redis:
    image: redis:7-alpine
    ports: ["6379:6379"]
    volumes: ["redis_data:/data"]
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 10s

  opensearch:
    image: opensearchproject/opensearch:2.11.0
    environment:
      - discovery.type=single-node
      - DISABLE_SECURITY_PLUGIN=true
    ports: ["9200:9200"]
    volumes: ["opensearch_data:/usr/share/opensearch/data"]

  fastapi:
    build:
      context: .
      dockerfile: Dockerfile.api
    ports: ["8000:8000"]
    environment:
      - AWS_REGION=us-east-1
      - REDIS_URL=redis://redis:6379
      - OPENSEARCH_URL=http://opensearch:9200
      - LANGCHAIN_TRACING_V2=true
      - LANGCHAIN_API_KEY=${LANGCHAIN_API_KEY}
    depends_on:
      redis:
        condition: service_healthy
    volumes:
      - ~/.aws:/root/.aws:ro

  streamlit:
    build:
      context: .
      dockerfile: Dockerfile.ui
    ports: ["8501:8501"]
    environment:
      - API_URL=http://fastapi:8000
    depends_on:
      - fastapi

volumes:
  redis_data:
  opensearch_data:
```

**Two Dockerfiles** (Dockerfile.api with Gunicorn + Uvicorn workers, Dockerfile.ui with Streamlit headless mode) and two requirements files keep images lean.

**Start everything:**
```bash
docker-compose up --build
# Open http://localhost:8501 — full dashboard
# Open http://localhost:8000/docs — FastAPI Swagger
```

---

## 4. Production Project Structure

```
kuber-underwriting/
├── kuber_api/                    # FastAPI + LangGraph
│   ├── main.py                     # FastAPI app entry
│   ├── orchestrator.py             # LangGraph builder
│   ├── agents/                     # 4 specialized agents
│   ├── tools/                      # 20+ tool implementations
│   ├── models/                     # State + Pydantic schemas
│   ├── middleware/                 # Auth, logging, metrics
│   └── config/                     # Settings, guardrails
├── dashboard/                      # Streamlit UI
│   ├── Home.py
│   ├── pages/                      # 3 views
│   ├── components/
│   └── utils/
├── evaluation/                     # Ragas + DeepEval + Bedrock Eval
│   ├── datasets/
│   ├── ragas_eval.py
│   ├── deepeval_tests.py
│   └── bedrock_eval.py
├── tests/                          # Unit + integration tests
├── docker-compose.yml
├── Dockerfile.api
├── Dockerfile.ui
├── Makefile
└── README.md
```

---

## 5. End-to-End Test Scenarios

### 5.1 Strong Application (Happy Path)

```json
{
  "application_id": "APP-STRONG-001",
  "borrower_data": {
    "fico": 780, "dti": 24.0,
    "monthly_income": 15000, "industry": "Technology",
    "employment_years": 8, "credit_history_years": 12
  }
}
```

**Expected:** All four agents complete. RiskScoring 82/100. Compliance passes. Recommendation: APPROVED. Time: ~12s. Cost: ~$0.03.

### 5.2 Weak Application (Denial Path)

```json
{
  "application_id": "APP-WEAK-002",
  "borrower_data": {
    "fico": 580, "dti": 52.0,
    "monthly_income": 4000, "industry": "Oil & Gas",
    "loan_amount": 450000, "property_value": 500000
  }
}
```

**Expected:** FICO below threshold. DTI exceeds QM limit. LTV 90% exceeds Texas 50(a)(6) 80% limit. Recommendation: DENIED. Compliance flags three violations.

### 5.3 Borderline Application (Human Review Path)

```json
{
  "application_id": "APP-BORDER-003",
  "borrower_data": {
    "fico": 680, "dti": 41.0,
    "monthly_income": 8333, "industry": "Oil & Gas",
    "loan_amount": 390000, "property_value": 500000
  }
}
```

**Expected:** Borderline FICO. DTI above 38% threshold, no compensating factors. Cyclical industry risk. LTV within limits. Recommendation: MANUAL_REVIEW. LangGraph interrupts at human review node.

---

## 6. Production Readiness Checklist

### Infrastructure
- [ ] ECS Fargate task definitions for FastAPI and Streamlit (separate services)
- [ ] ALB configured with health check on `/health` every 30s
- [ ] Redis (ElastiCache) with encryption at rest
- [ ] OpenSearch domain with VPC access
- [ ] IAM roles with Bedrock, S3, SQS permissions
- [ ] Security groups: Streamlit → FastAPI → Redis/OpenSearch/Bedrock
- [ ] Auto-scaling: min 2 / max 8 tasks (60% scale up, 30% scale down)

### Application
- [ ] Environment variables via AWS Secrets Manager (not .env files)
- [ ] Structured logging with correlation IDs
- [ ] Prometheus metrics endpoint for CloudWatch custom metrics
- [ ] Graceful shutdown handling
- [ ] Request validation on all endpoints

### Observability
- [ ] Langfuse tracing for production (LangSmith for development)
- [ ] Ragas evaluation dataset with 500+ test cases
- [ ] DeepEval quality gates in GitLab CI/CD pipeline
- [ ] Bedrock AgentCore Evaluations for agent-specific checks
- [ ] CloudWatch dashboards: count, latency P95, error rate, cost
- [ ] Alerts: faithfulness drop > 2%, error rate > 5%, latency P95 > 30s

### Cost Optimization
- [ ] Prompt caching enabled (84% input cost savings)
- [ ] Extended thinking enabled for Compliance agent only
- [ ] Model routing: Haiku for simple tasks, Sonnet for complex
- [ ] Batch similar loan types for cache hit rate

### Security
- [ ] the company JWT authentication on all FastAPI endpoints
- [ ] Streamlit behind auth proxy (ALB + Cognito)
- [ ] CORS restricted to the company domains
- [ ] Audit trail for every evaluation and human decision
- [ ] Bedrock Guardrails for PII redaction
- [ ] No sensitive data in logs

### Testing
- [ ] Unit tests for each agent
- [ ] Integration tests for LangGraph pipeline (3 scenarios)
- [ ] API tests for FastAPI endpoints
- [ ] Evaluation tests (Ragas + DeepEval) passing
- [ ] Load test: 50 concurrent evaluations without degradation

---

## 7. System Capabilities Summary

- 4 specialized AI agents with optimal model selection (Claude Haiku + Sonnet)
- 20+ tools across calculations, RAG, knowledge graph, document processing
- LangGraph orchestrator with parallel execution, conditional routing, human-in-the-loop
- Redis checkpointing for crash recovery
- Textract hybrid for cost-optimized document processing (47% savings)
- Bedrock Guardrails for content safety and PII protection
- Retry + circuit breaker for resilience (99.8% effective reliability)
- Smart RAG (Strategy 5) + Agentic RAG (Strategy 6) for compliance
- Prompt caching (84% input cost savings)
- Extended thinking for complex regulatory reasoning
- FastAPI REST API with async submit/poll pattern
- Streamlit dashboard with real-time monitoring and human review
- Langfuse tracing + Ragas evaluation + Bedrock AgentCore checks
- DeepEval CI/CD quality gates
- Docker Compose for local dev, ECS Fargate for production

---

## 8. Estimated Production Metrics

| Metric | Target |
|--------|--------|
| Cost per evaluation | $0.025–$0.035 |
| Latency (automated) | 10–15 seconds |
| Latency (with human review) | 12–20 seconds + review time |
| Effective reliability | 99.8% |
| Document processing cost reduction | 47% (vs all-Vision) |
| Faithfulness score | > 0.95 |
| Human review rate | ~15% of evaluations |
| Daily evaluation capacity | 1,000+ (auto-scaling to 8 tasks) |

---

## 9. The Production Metrics Dashboard

What the company's leadership sees daily:

```
┌──────────────────────────────────────────────────────┐
│         KUBER AI UNDERWRITING METRICS               │
│                                                       │
│  Today's Evaluations: 847    │  Cost: $25.41          │
│  Avg Latency: 12.3s          │  Cost/Eval: $0.030     │
│  Error Rate: 0.4%            │  Human Reviews: 127     │
│                                                       │
│  Recommendation Distribution                          │
│  ████████████████░░░░ APPROVED (68%)                  │
│  ███░░░░░░░░░░░░░░░░ DENIED (12%)                    │
│  ████░░░░░░░░░░░░░░░ MANUAL_REVIEW (15%)             │
│  █░░░░░░░░░░░░░░░░░░ ERROR (5%)                      │
│                                                       │
│  Quality Scores (Ragas - Weekly):                     │
│  Faithfulness:      0.96 ▲ (+0.01)                    │
│  Context Recall:    0.91 ─                            │
│  Answer Relevancy:  0.94 ▲ (+0.02)                    │
│  Context Precision: 0.89 ▼ (-0.01)                    │
│                                                       │
│  Agent Performance:                                   │
│  FetchData:    2.1s avg │ $0.002/call │ 0.1% error    │
│  DocReview:    4.8s avg │ $0.008/call │ 0.3% error    │
│  RiskScoring:  2.9s avg │ $0.004/call │ 0.2% error    │
│  Compliance:   3.5s avg │ $0.012/call │ 0.1% error    │
└──────────────────────────────────────────────────────┘
```

---

## 10. Key Takeaways

1. **Six weeks built a complete production AI system:** foundation → individual agents → orchestration → hardening → evaluation → deployment.

2. **The integration is the value** — each component is necessary but not sufficient. The system delivers production value only when all four layers work together.

3. **Docker Compose gives you a complete local stack** with one command. Production deploys the same containers to ECS Fargate.

4. **Three test scenarios** (strong, weak, borderline) validate the entire pipeline end-to-end. Run on every deployment.

5. **The production readiness checklist has six categories.** Most items are gaps to address before the company production deployment — prioritize observability, security, and authentication.

6. **Estimated production metrics:** $0.025–$0.035 per evaluation, 10–15 second latency, 99.8% reliability, ~15% human review rate.

---

## 11. What Comes Next

**Plan completion:** Six weeks complete. The structured GenAI mastery plan ends here. You now have hands-on experience with: prompt engineering, structured output, RAG (5 strategies), agentic RAG, vision processing, knowledge graphs, multi-agent orchestration, production hardening, evaluation, model optimization, deployment, and human-in-the-loop UIs.

**the company production path:** Address the gaps in the production readiness checklist. Coordinate with the company's AI platform team for ECS Fargate deployment, IAM roles, Secrets Manager, and CloudWatch integration. Establish the model versioning and retraining pipeline.

**Continued learning:** The reading track from your original plan — *AI Engineering* by Chip Huyen, *Designing Multi-Agent Systems* by Victor Dibia, *Building Agentic AI Systems* by Talukdar and Biswas — provides depth on topics covered briefly here.

**Career impact:** You set a goal in early 2026 to become a GenAI expert by April 30 through hands-on construction. With Kuber's multi-agent system architecturally complete and production-ready (pending the deployment checklist), you have both the theoretical foundation and the production-grade artifact to demonstrate mastery.
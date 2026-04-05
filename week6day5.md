# Week 6, Day 5: Streamlit UI — Agent Progress, Audit Trails & Human Review

**Date:** April 5, 2026  
**Module:** Frontend & UI  
**Platform:** Kuber Loan Origination System  

---

## 1. Session Overview

**Topic:** Streamlit production dashboard — building the three-view operator interface (Submit, Monitor, Review) that connects to the FastAPI service, shows real-time agent progress, displays evaluation results with expandable agent reports, and enables human-in-the-loop decision-making.

**Prerequisites:** Week 6 Day 4 complete (FastAPI with async submit/poll, SSE streaming, health checks). Phase 3 basic Streamlit experience.

**Key Deliverable:** A production-ready internal dashboard for the company underwriters to interact with the AI evaluation pipeline.

### Implemented Contract In This Repo

The current implementation now matches this simplified API/UI split:

- `POST /evaluate`
    - accepts one application
    - returns `202 Accepted` with `job_id`
- `GET /status?job_id=...`
    - returns current agent, job state, and progress percent
- `GET /result?job_id=...`
    - returns final evaluation payload once complete
- `GET /health`
    - liveness check
- `GET /evaluate/history?application_id=...`
    - returns past completed evaluations for the History screen

The Streamlit dashboard in this repo provides:

- `Submit`
- `Monitor`
- `Review`
- `History`

---

## 2. What Streamlit Is

Streamlit is a Python library that turns scripts into web apps. No HTML, CSS, or JavaScript required. Purpose-built for data science dashboards and internal tools.

**Critical mental model:** Unlike React or Angular, Streamlit has **no component lifecycle**. The entire script re-runs top-to-bottom every time the user clicks anything. Variables are lost between reruns. Use `st.session_state` to persist data — like `HttpSession` in Spring or `useState` in React.

| Streamlit | When to Use |
|-----------|-------------|
| Internal tools, dashboards, demos | the company underwriter dashboard (current need) |
| Single developer, days to build | POC and initial production, iterate fast |
| Python-only, no frontend team needed | Your team is Python + Java, not React |
| Rebuild in React later if needed | When dashboard goes external-facing |

---

## 3. Dashboard Architecture

Three primary views, plus history:

- **View 1 — Submit Evaluation:** Enter borrower and loan fields, submit to FastAPI, receive `job_id` immediately.
- **View 2 — Monitor Pipeline:** Agent progress tracking across FetchData, DocReview, RiskScoring, and Compliance. Polls `GET /status`.
- **View 3 — Review Results:** Pulls final output from `GET /result`, shows risk summary, agent reports, audit trail, and human decision buttons.
- **View 4 — History:** Pulls prior runs from `GET /evaluate/history`.

---

## 4. View 1: Submit New Evaluation

```python
import streamlit as st
import httpx

API_URL = "http://localhost:8000"

st.header("Submit Loan Evaluation")

col1, col2 = st.columns(2)

with col1:
    st.subheader("Loan Details")
    app_id = st.text_input("Application ID", value="APP-001")
    loan_type = st.selectbox("Loan Type", ["conventional", "fha", "va", "home_equity"])
    jurisdiction = st.selectbox("Jurisdiction", ["TX", "CA", "NY", "FL"])
    loan_amount = st.number_input("Loan Amount ($)", value=500000, step=10000)

with col2:
    st.subheader("Borrower Details")
    fico = st.number_input("FICO Score", value=710, min_value=300, max_value=850)
    dti = st.number_input("DTI Ratio (%)", value=41.0, step=0.1)
    income = st.number_input("Monthly Income ($)", value=8333, step=100)
    industry = st.selectbox("Industry", ["Technology", "Oil & Gas", "Healthcare"])

uploaded_files = st.file_uploader("Upload loan documents", accept_multiple_files=True, type=["pdf"])

if st.button("Submit for AI Evaluation", type="primary"):
    with st.spinner("Submitting..."):
        response = httpx.post(f"{API_URL}/evaluate", json={
            "application_id": app_id,
            "loan_type": loan_type,
            "jurisdiction": jurisdiction,
            "borrower_data": {"fico": fico, "dti": dti, "monthly_income": income, "industry": industry},
            "documents": [],
        })
        if response.status_code == 202:
            result = response.json()
            st.session_state["active_job_id"] = result["job_id"]
            st.success(f"Submitted! Job ID: {result['job_id']}")
```

---

## 5. View 2: Monitor Pipeline

```python
import time

st.header("Pipeline Monitor")
job_id = st.text_input("Job ID", value=st.session_state.get("active_job_id", ""))

if job_id and st.button("Track Evaluation"):
    agent_cols = st.columns(4)
    agents = ["FetchData", "DocReview", "RiskScoring", "Compliance"]
    agent_status = {a: agent_cols[i].empty() for i, a in enumerate(agents)}
    progress_bar = st.progress(0)
    
    while True:
        response = httpx.get(f"{API_URL}/evaluate/{job_id}/status")
        status = response.json()
        current_agent = status.get("current_agent", "")
        progress = status.get("progress_pct", 0)
        
        for i, agent in enumerate(agents):
            if agent == current_agent:
                agent_status[agent].markdown(f"**{agent}**\n\n🔄 Running...")
            elif progress > (i + 1) * 25:
                agent_status[agent].markdown(f"**{agent}**\n\n✅ Complete")
            else:
                agent_status[agent].markdown(f"**{agent}**\n\n⏳ Pending")
        
        progress_bar.progress(min(progress, 100))
        
        if status["status"] in ("COMPLETE", "FAILED"):
            break
        time.sleep(2)
    
    if status["status"] == "COMPLETE":
        st.success("Evaluation complete!")
        st.balloons()
```

Uses polling (GET /status every 2 seconds) rather than SSE. Streamlit's full-rerun model makes SSE complex; polling is simpler and sufficient for 2-second intervals.

---

## 6. View 3: Review Results (Human-in-the-Loop)

### 6.1 Summary Metrics Bar

```python
result = st.session_state["result"]

col1, col2, col3, col4 = st.columns(4)
col1.metric("Recommendation", result["recommendation"])
col2.metric("Risk Score", f"{result['risk_score']}/100")
col3.metric("DTI Ratio", f"{result['dti_ratio']:.1f}%")
col4.metric("Compliance", result["compliance_status"])
```

### 6.2 Expandable Agent Reports

```python
for agent_name, report in result["agent_reports"].items():
    with st.expander(f"📋 {agent_name} Agent Report"):
        st.markdown(report.get("summary", ""))
        
        if "findings" in report:
            for finding in report["findings"]:
                icon = "✅" if finding["status"] == "PASS" else "❌"
                st.markdown(f"- {icon} {finding['description']}")
        
        if "tool_calls" in report:
            for tool in report["tool_calls"]:
                st.code(f"{tool['name']}({tool['input']}) → {tool['output'][:100]}...")
```

### 6.3 Audit Trail

```python
import pandas as pd
audit_df = pd.DataFrame(result["audit_trail"])
st.dataframe(audit_df, use_container_width=True)
```

### 6.4 Human Decision Interface

```python
if result["recommendation"] == "MANUAL_REVIEW":
    st.warning("This evaluation requires human review.")
    
    decision = st.radio(
        "Your decision:",
        ["Approve with Conditions", "Deny", "Request More Information"],
        horizontal=True
    )
    conditions = st.text_area("Conditions / Notes")
    
    if st.button("Submit Decision", type="primary"):
        httpx.post(f"{API_URL}/evaluate/{job_id}/review", json={
            "decision": decision,
            "conditions": conditions,
            "reviewer": "underwriter@thecompany.com",
        })
        st.success("Decision recorded.")

elif result["recommendation"] == "DENIED":
    col_a, col_b = st.columns(2)
    with col_a:
        if st.button("Confirm Denial"): st.info("Denial confirmed.")
    with col_b:
        if st.button("Override to Approve"):
            override_reason = st.text_area("Justification:")
            if st.button("Submit Override"):
                st.success("Override recorded with justification.")
```

---

## 7. Session State — The Critical Pattern

```python
# WRONG — lost on every rerun
job_id = "abc-123"  # Gone when user clicks anything

# RIGHT — persisted across reruns
st.session_state["job_id"] = "abc-123"  # Survives clicks

# Check before using
if "result" in st.session_state:
    display_result(st.session_state["result"])
```

**Java analogy:** `st.session_state` is like `HttpSession` in Spring — data scoped to the user's browser session, survives across requests. Every Streamlit rerun is like a new HTTP request hitting your controller.

---

## 8. Multi-Page App Structure

```
kuber-dashboard/
├── Home.py                      # Main entry point
├── pages/
│   ├── 1_Submit_Evaluation.py   # View 1
│   ├── 2_Monitor_Pipeline.py    # View 2
│   └── 3_Review_Results.py      # View 3
├── components/                  # Reusable UI components
├── utils/
│   ├── api_client.py            # FastAPI client wrapper
│   └── auth.py                  # the company SSO integration
└── .streamlit/
    └── config.toml              # Theme, server settings
```

Streamlit auto-discovers files in `pages/` and creates sidebar navigation.

---

## 9. Running the Full Stack

```bash
# Terminal 1: Redis
docker run -d -p 6379:6379 redis:7

# Terminal 2: FastAPI server
uvicorn kuber_api.main:app --reload --port 8000

# Terminal 3: Streamlit dashboard
streamlit run Home.py --server.port 8501
```

For production: separate ECS Fargate containers. Streamlit hits FastAPI via internal ALB DNS. Streamlit is NOT internet-exposed — accessible only through the company's internal network.

---

## 10. Streamlit vs Alternatives

| Tool | Type | Best For | Kuber Fit |
|------|------|----------|-------------|
| **Streamlit** | Python-native | Internal dashboards, demos | ✅ Perfect for underwriting dashboard |
| **Gradio** | Python-native | ML model demos | ❌ Too focused on model I/O |
| **React** | Full frontend | Production user-facing apps | 🔄 Future: if dashboard goes external |
| **Retool** | Low-code | Admin panels, CRUD | ❌ Too limited for agent visualization |
| **Dash (Plotly)** | Python-native | Data visualization dashboards | 🔄 Alternative if heavy charts needed |

---

## 11. Questions & Answers

### Q: Why Streamlit instead of React for the company?

Streamlit is right for an internal underwriting dashboard because: (1) your team is Python + Java, not React, (2) days to build vs weeks, (3) sufficient for internal the company users, (4) the FastAPI backend is frontend-agnostic — rebuild in React later without changing the API. Rebuild triggers: dashboard becomes external-facing, need complex interactivity, have a dedicated frontend team, or need pixel-perfect brand compliance.

### Q: How to add the company SSO to Streamlit?

Two approaches: (1) `streamlit-authenticator` library for simple LDAP integration. (2) Put Streamlit behind the company's existing auth proxy (ALB + Cognito or OAuth2 proxy). The proxy handles authentication before traffic reaches Streamlit. This is cleaner — no auth code in the Streamlit app itself.

### Q: Same container or separate for FastAPI and Streamlit?

Separate containers. Different scaling profiles: FastAPI scales on evaluation load (CPU-intensive LLM calls), Streamlit scales on concurrent users (memory-per-session). In ECS Fargate, they're separate services in the same cluster communicating via internal ALB.

### Q: Streamlit limitations for 30-person team?

Three limitations: (1) **Memory** — each session holds state in server memory. 30 concurrent users could consume significant RAM. Mitigate by storing results in Redis. (2) **Concurrency** — separate thread per user but shared process. Keep heavy work in FastAPI. (3) **Interactivity** — full-rerun model makes drag-and-drop, inline editing, real-time collaboration difficult. For 30 underwriters doing review and approval, these are manageable.

### Q: When to rebuild in React?

Four triggers: (1) External-facing dashboard, (2) Complex interactivity (drag-and-drop, inline annotation), (3) 100+ concurrent users causing performance issues, (4) Pixel-perfect design requirements from the company's design team. The FastAPI backend remains unchanged.

---

## 12. Key Takeaways

1. **Streamlit is the right choice** for Kuber's internal underwriting dashboard — Python-native, days to build, sufficient for internal users.

2. **Three-view architecture** (Submit, Monitor, Review) covers the full underwriter workflow from submission to human decision-making.

3. **st.session_state is critical** — without it, all data is lost on every interaction. Use it like HttpSession in Spring.

4. **The Review view** with expandable agent reports, audit trail, and decision buttons provides the transparency the company's risk committee requires.

5. **Deploy as separate Fargate containers** — FastAPI and Streamlit have different scaling profiles.

6. **FastAPI backend is frontend-agnostic** — rebuild in React later without changing the API contract.

---

## 13. Next Session Preview

**Week 6, Weekend: Final Integration & Deployment Build**

Topics: Connecting all components (FastAPI + LangGraph + Streamlit + Redis + Bedrock + OpenSearch), end-to-end testing with real loan scenarios, Docker Compose for local development, ECS Fargate deployment, and the production readiness checklist.

Connection: This week we built evaluation (Days 1–2), model optimization (Day 3), the API layer (Day 4), and the UI (Day 5). The weekend ties everything together into a deployable system.x
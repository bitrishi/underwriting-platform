from fastapi.testclient import TestClient

from src.api.history_store import EvaluationHistoryStore
from src.api.job_store import EvaluationJobStore
from src.api.server import app, get_chain, get_history_store, get_job_store
from src.models.decision import LoanDecision


class FakeChain:
    def evaluate_safe(self, application):
        return LoanDecision(
            decision="APPROVED",
            confidence=0.94,
            risk_level="LOW",
            reasons=[f"FICO {application.fico_score} meets threshold"],
            conditions=None,
            criteria=None,
            reasoning_trace=None,
        )


class InMemoryHistoryStore(EvaluationHistoryStore):
    def __init__(self):
        super().__init__(redis_url=None)


def test_evaluate_status_result_flow():
    store = InMemoryHistoryStore()
    job_store = EvaluationJobStore()
    app.dependency_overrides[get_chain] = lambda: FakeChain()
    app.dependency_overrides[get_history_store] = lambda: store
    app.dependency_overrides[get_job_store] = lambda: job_store

    client = TestClient(app)
    response = client.post(
        "/evaluate",
        json={
            "application_id": "APP-010",
            "borrower_data": {
                "fico": 735,
                "dti": 36,
                "income": 125000,
                "loan_amount": 320000,
            },
        },
    )

    assert response.status_code == 202
    accepted = response.json()
    assert accepted["status"] == "QUEUED"
    job_id = accepted["job_id"]

    status_response = client.get("/status", params={"job_id": job_id})
    assert status_response.status_code == 200
    status_payload = status_response.json()
    assert status_payload["status"] == "COMPLETE"
    assert status_payload["progress_pct"] == 100

    result_response = client.get("/result", params={"job_id": job_id})
    assert result_response.status_code == 200
    result_payload = result_response.json()
    assert result_payload["status"] == "COMPLETE"
    assert result_payload["result"]["application_id"] == "APP-010"
    assert result_payload["result"]["decision"]["decision"] == "APPROVED"

    app.dependency_overrides.clear()


def test_batch_evaluate_and_history_round_trip():
    store = InMemoryHistoryStore()
    job_store = EvaluationJobStore()
    app.dependency_overrides[get_chain] = lambda: FakeChain()
    app.dependency_overrides[get_history_store] = lambda: store
    app.dependency_overrides[get_job_store] = lambda: job_store

    client = TestClient(app)
    payload = {
        "applications": [
            {
                "application_id": "APP-001",
                "borrower_data": {
                    "fico": 740,
                    "dti": 0.31,
                    "income": 120000,
                    "loan_amount": 350000,
                },
            },
            {
                "application_id": "APP-002",
                "borrower_data": {
                    "fico": 690,
                    "dti": 42,
                    "income": 98000,
                },
            },
        ]
    }

    batch_response = client.post("/evaluate/batch", json=payload)

    assert batch_response.status_code == 200
    body = batch_response.json()
    assert body["success_count"] == 2
    assert body["failure_count"] == 0
    assert body["results"][0]["status"] == "success"
    assert body["results"][1]["decision"]["decision"] == "APPROVED"
    assert body["results"][0]["risk_score"] >= 0
    assert len(body["results"][0]["agent_reports"]) == 4
    assert len(body["results"][0]["audit_trail"]) == 4

    history_response = client.get("/evaluate/history", params={"application_id": "APP-001"})

    assert history_response.status_code == 200
    history = history_response.json()
    assert history["application_id"] == "APP-001"
    assert len(history["evaluations"]) == 1
    assert history["evaluations"][0]["decision"]["risk_level"] == "LOW"
    assert history["evaluations"][0]["human_decision_status"] == "PENDING"

    app.dependency_overrides.clear()


def test_batch_validation_rejects_missing_required_borrower_fields():
    client = TestClient(app)

    response = client.post(
        "/evaluate/batch",
        json={
            "applications": [
                {
                    "application_id": "APP-003",
                    "borrower_data": {
                        "dti": 0.4,
                        "income": 85000,
                    },
                }
            ]
        },
    )

    assert response.status_code == 422
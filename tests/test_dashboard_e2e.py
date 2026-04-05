from __future__ import annotations

import os
import time

from streamlit.testing.v1 import AppTest


os.environ.setdefault("UNDERWRITING_API_URL", "http://localhost:8000")


def _submit_case(
    at: AppTest,
    application_id: str,
    borrower_name: str,
    fico: int,
    dti: float,
    income: float,
    employment_years: float,
    loan_amount: float,
    property_value: float,
) -> str:
    at.radio[0].set_value("Submit")
    at.run()

    at.text_input[0].set_value(application_id)
    at.text_input[1].set_value(borrower_name)
    at.number_input[0].set_value(fico)
    at.number_input[1].set_value(dti)
    at.number_input[2].set_value(income)
    at.number_input[3].set_value(employment_years)
    at.number_input[4].set_value(loan_amount)
    at.number_input[5].set_value(property_value)
    at.button[0].click()
    at.run(timeout=15)

    assert at.session_state["active_job_id"]
    return at.session_state["active_job_id"]


def _monitor_until_complete(at: AppTest, job_id: str, expected_application_id: str) -> dict:
    deadline = time.time() + 20
    while time.time() < deadline:
        at.radio[0].set_value("Monitor")
        at.run(timeout=15)
        at.selectbox[0].set_value(job_id)
        at.checkbox[0].set_value(False)
        at.run(timeout=15)

        latest = at.session_state["latest_result"] if "latest_result" in at.session_state else None
        if latest and latest.get("application_id") == expected_application_id:
            return latest
        time.sleep(0.2)

    raise AssertionError(f"Job {job_id} did not complete in time")


def _load_review(at: AppTest, job_id: str) -> dict:
    at.radio[0].set_value("Review")
    at.run(timeout=15)
    at.selectbox[0].set_value(job_id)
    at.run(timeout=15)
    latest = at.session_state["latest_result"] if "latest_result" in at.session_state else None
    assert latest is not None
    return latest


def test_streamlit_submit_monitor_review_e2e():
    at = AppTest.from_file("src/dashboard/app.py", default_timeout=20)
    at.run(timeout=15)

    scenarios = [
        (
            "APP-001",
            "Alice Strong",
            740,
            24.0,
            120000.0,
            5.0,
            350000.0,
            440000.0,
            "APPROVED",
        ),
        (
            "APP-002",
            "Bob Risky",
            620,
            48.0,
            55000.0,
            0.5,
            280000.0,
            290000.0,
            "DENIED",
        ),
        (
            "APP-003",
            "Carol Borderline",
            685,
            41.0,
            85000.0,
            2.0,
            310000.0,
            365000.0,
            "MANUAL_REVIEW",
        ),
    ]

    job_ids: dict[str, str] = {}
    for app_id, borrower_name, fico, dti, income, employment_years, loan_amount, property_value, _ in scenarios:
        job_ids[app_id] = _submit_case(
            at,
            application_id=app_id,
            borrower_name=borrower_name,
            fico=fico,
            dti=dti,
            income=income,
            employment_years=employment_years,
            loan_amount=loan_amount,
            property_value=property_value,
        )

    for app_id, _, _, _, _, _, _, _, expected in scenarios:
        result = _monitor_until_complete(at, job_ids[app_id], app_id)
        assert result["recommendation"] == expected

        reviewed = _load_review(at, job_ids[app_id])
        assert reviewed["recommendation"] == expected

    borderline_job = job_ids["APP-003"]
    _load_review(at, borderline_job)
    at.button[2].click()
    at.run(timeout=15)
    assert at.session_state["human_decisions"]["APP-003"] == "MANUAL_REVIEW"
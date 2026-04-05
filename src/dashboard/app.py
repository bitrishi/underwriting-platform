from __future__ import annotations

import time
from typing import Any

import requests
import streamlit as st

from src.dashboard.utils import (
    build_pdf_report,
    get_evaluation_history,
    get_job_result,
    get_job_status,
    get_risk_color,
    get_risk_label,
    submit_evaluation,
)


st.set_page_config(page_title="Underwriting Dashboard", page_icon="🏦", layout="wide")


AGENT_ORDER = ["FetchData", "DocReview", "RiskScoring", "Compliance"]


def _init_state() -> None:
    st.session_state.setdefault("submitted_jobs", [])
    st.session_state.setdefault("active_job_id", None)
    st.session_state.setdefault("latest_result", None)
    st.session_state.setdefault("selected_evaluation", None)
    st.session_state.setdefault("human_decisions", {})


def _render_risk_badge(risk_score: int) -> None:
    color = get_risk_color(risk_score)
    label = get_risk_label(risk_score)
    st.markdown(
        f"<div style='padding:0.6rem 0.9rem;border-radius:0.6rem;background:{color};color:white;display:inline-block;font-weight:600;'>"
        f"Risk Score: {risk_score} ({label})"
        "</div>",
        unsafe_allow_html=True,
    )


def _select_evaluation_from_latest() -> dict[str, Any] | None:
    latest_result = st.session_state.get("latest_result")
    if not latest_result:
        return None
    st.session_state["selected_evaluation"] = latest_result
    return latest_result


def _render_submit_view() -> None:
    st.header("Submit")
    st.caption("Submit a loan application to the FastAPI server. The server returns a job ID immediately.")

    with st.form("submit_form", clear_on_submit=False):
        col1, col2, col3 = st.columns(3)
        application_id = col1.text_input("Application ID", value=f"APP-{len(st.session_state['submitted_jobs']) + 1:03d}")
        borrower_name = col2.text_input("Borrower Name", value="")
        fico = col3.number_input("FICO", min_value=300, max_value=850, value=720, step=1)

        col4, col5, col6 = st.columns(3)
        dti = col4.number_input("DTI (%)", min_value=0.0, max_value=100.0, value=36.0, step=0.1)
        income = col5.number_input("Annual Income", min_value=1.0, value=120000.0, step=1000.0)
        employment_years = col6.number_input("Employment Years", min_value=0.0, value=3.0, step=0.5)

        col7, col8 = st.columns(2)
        loan_amount = col7.number_input("Loan Amount", min_value=1.0, value=350000.0, step=5000.0)
        property_value = col8.number_input("Property Value", min_value=1.0, value=440000.0, step=5000.0)

        submit_job = st.form_submit_button("Submit Evaluation", type="primary")

    if submit_job:
        payload = {
            "application_id": application_id,
            "borrower_data": {
                "borrower_name": borrower_name,
                "fico": int(fico),
                "dti": float(dti),
                "income": float(income),
                "loan_amount": float(loan_amount),
                "property_value": float(property_value),
                "employment_years": float(employment_years),
            },
        }
        with st.spinner("Submitting evaluation job..."):
            try:
                response = submit_evaluation(payload)
                st.session_state["active_job_id"] = response["job_id"]
                st.session_state["submitted_jobs"].insert(0, response)
                st.session_state["latest_result"] = None
                st.success(f"Submitted {application_id}. Job ID: {response['job_id']}")
            except requests.RequestException as exc:
                st.error(f"Evaluation submission failed: {exc}")

    if st.session_state["submitted_jobs"]:
        st.subheader("Submitted Jobs")
        st.dataframe(st.session_state["submitted_jobs"], use_container_width=True)


def _render_monitor_view() -> None:
    st.header("Monitor")
    job_options = [item["job_id"] for item in st.session_state.get("submitted_jobs", [])]
    default_job = st.session_state.get("active_job_id")
    job_id = st.selectbox("Job ID", job_options, index=job_options.index(default_job) if default_job in job_options else 0) if job_options else ""
    auto_refresh = st.checkbox("Auto refresh every 2s", value=True)

    if not job_id:
        st.info("Submit an evaluation first to monitor agent progress.")
        return

    try:
        status = get_job_status(job_id)
    except requests.RequestException as exc:
        st.error(f"Status lookup failed: {exc}")
        return

    st.subheader(status["application_id"])
    st.caption(f"Job status: {status['status']}")
    progress = st.progress(int(status["progress_pct"]), text=f"Current agent: {status.get('current_agent') or 'None'}")
    agent_cols = st.columns(len(AGENT_ORDER))
    for index, agent_name in enumerate(AGENT_ORDER):
        state = status["agent_progress"].get(agent_name, "PENDING")
        icon = {"COMPLETED": "✅", "RUNNING": "🔄", "PENDING": "⏳"}.get(state, "⚪")
        agent_cols[index].markdown(f"**{agent_name}**\n\n{icon} {state.title()}")

    if status["status"] == "COMPLETE":
        result = get_job_result(job_id)
        if result is not None:
            st.session_state["latest_result"] = result
            _render_risk_badge(int(result.get("risk_score", 0)))
            st.success("Evaluation complete. Open Review to inspect the full result.")
    elif status["status"] == "FAILED":
        st.error(status.get("error") or "Evaluation failed.")
    elif auto_refresh:
        time.sleep(2)
        st.rerun()


def _render_review_view() -> None:
    st.header("Review")
    job_options = [item["job_id"] for item in st.session_state.get("submitted_jobs", [])]
    if job_options:
        selected_job = st.selectbox("Job ID", job_options, key="review_job_id")
        try:
            latest = get_job_result(selected_job)
            if latest is not None:
                st.session_state["latest_result"] = latest
                st.session_state["active_job_id"] = selected_job
        except requests.RequestException:
            pass

    evaluation = _select_evaluation_from_latest()
    if not evaluation:
        st.info("No completed evaluation available yet. Wait for Monitor to finish the job.")
        return

    _render_risk_badge(int(evaluation.get("risk_score", 0)))
    st.write("")
    st.write(f"Recommendation: {evaluation.get('recommendation', 'UNKNOWN')}")
    st.write(f"Decision: {evaluation['decision']['decision']}")
    st.write(f"Confidence: {evaluation['decision']['confidence']:.2f}")

    for report in evaluation.get("agent_reports", []):
        with st.expander(f"{report['agent_name']} Report", expanded=report["agent_name"] == "RiskScoring"):
            st.write(report["summary"])
            st.json(report["details"])

    with st.expander("Audit Trail", expanded=True):
        for event in evaluation.get("audit_trail", []):
            st.markdown(f"**{event['step']}** [{event['status']}]  ")
            st.caption(f"{event['timestamp']} | {event['detail']}")

    col1, col2, col3 = st.columns(3)
    if col1.button("Approve", use_container_width=True):
        st.session_state["human_decisions"][evaluation["application_id"]] = "APPROVE"
    if col2.button("Deny", use_container_width=True):
        st.session_state["human_decisions"][evaluation["application_id"]] = "DENY"
    if col3.button("Manual Review", use_container_width=True):
        st.session_state["human_decisions"][evaluation["application_id"]] = "MANUAL_REVIEW"

    decision = st.session_state["human_decisions"].get(evaluation["application_id"], "PENDING")
    st.caption(f"Human decision: {decision}")

    pdf_bytes = build_pdf_report(evaluation)
    st.download_button(
        "Download Report",
        data=pdf_bytes,
        file_name=f"{evaluation['application_id']}_evaluation_report.pdf",
        mime="application/pdf",
        type="primary",
    )


def _render_history_view() -> None:
    st.header("History")
    application_id = st.text_input("Application ID", value="APP-001")
    if st.button("Fetch History"):
        try:
            history = get_evaluation_history(application_id)
            evaluations = history.get("evaluations", [])
            if not evaluations:
                st.warning("No evaluations found for that application ID.")
                return

            for evaluation in evaluations:
                with st.container(border=True):
                    st.subheader(evaluation["application_id"])
                    _render_risk_badge(int(evaluation.get("risk_score", 0)))
                    st.caption(evaluation["evaluated_at"])
                    st.write(f"Recommendation: {evaluation.get('recommendation', 'UNKNOWN')}")
                    st.write(f"Decision: {evaluation['decision']['decision']}")
                    st.write(f"Reasons: {', '.join(evaluation['decision'].get('reasons', []))}")
                    st.write(f"Human decision status: {evaluation.get('human_decision_status', 'PENDING')}")
        except requests.RequestException as exc:
            st.error(f"History lookup failed: {exc}")


def main() -> None:
    _init_state()
    st.title("Kuber Underwriting Dashboard")
    st.caption("Submit, monitor, review, and audit underwriting evaluations from a single interface.")

    view = st.sidebar.radio("View", ["Submit", "Monitor", "Review", "History"])
    st.sidebar.markdown("---")
    st.sidebar.caption("API-driven dashboard backed by /evaluate endpoints.")

    if view == "Submit":
        _render_submit_view()
    elif view == "Monitor":
        _render_monitor_view()
    elif view == "Review":
        _render_review_view()
    else:
        _render_history_view()


if __name__ == "__main__":
    main()
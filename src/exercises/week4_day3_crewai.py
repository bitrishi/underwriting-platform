"""Week 4 Day 3: simple 2-agent CrewAI example for underwriting."""

from __future__ import annotations

import json
from typing import Any

from crewai import Agent, Crew, Process, Task
from crewai.tools import tool

from src.tools.fetch_tools import pull_borrower_data as lc_pull_borrower_data
from src.tools.fetch_tools import pull_credit_report as lc_pull_credit_report
from src.tools.underwriting_tools import calculate_dti as lc_calculate_dti
from src.tools.underwriting_tools import check_fico_eligibility as lc_check_fico_eligibility


def _to_json_text(data: Any) -> str:
    return json.dumps(data, sort_keys=True)


@tool("pull_borrower_data")
def pull_borrower_data(app_id: str) -> str:
    """Fetch borrower profile by application ID."""
    return _to_json_text(lc_pull_borrower_data.invoke({"app_id": app_id}))


@tool("pull_credit")
def pull_credit(ssn_last_four: str) -> str:
    """Fetch credit report by SSN last four digits."""
    return _to_json_text(lc_pull_credit_report.invoke({"ssn_last_four": ssn_last_four}))


@tool("calculate_dti")
def calculate_dti(annual_income: float, monthly_debt: float) -> str:
    """Calculate DTI ratio and return pass/fail metadata."""
    return _to_json_text(
        lc_calculate_dti.invoke(
            {"annual_income": annual_income, "monthly_debt": monthly_debt}
        )
    )


@tool("check_fico")
def check_fico(fico_score: int) -> str:
    """Check credit tier and minimum-eligibility status."""
    return _to_json_text(lc_check_fico_eligibility.invoke({"fico_score": fico_score}))


def _build_crew() -> tuple[Crew, Task, Task]:
    data_analyst = Agent(
        role="Data Analyst",
        goal="Fetch borrower and credit data needed for underwriting.",
        backstory="You gather the minimum reliable data for a risk decision.",
        tools=[pull_borrower_data, pull_credit],
        allow_delegation=False,
        verbose=False,
    )

    risk_assessor = Agent(
        role="Risk Assessor",
        goal="Assess underwriting risk with DTI and FICO checks.",
        backstory="You convert borrower/credit data into a clear risk recommendation.",
        tools=[calculate_dti, check_fico],
        allow_delegation=False,
        verbose=False,
    )

    fetch_data_task = Task(
        description=(
            "Use pull_borrower_data with app_id '{app_id}'. Then call pull_credit "
            "with the borrower ssn_last_four from the fetched profile. Return strict JSON "
            "with keys: borrower, credit."
        ),
        expected_output="Strict JSON object: {\"borrower\": {...}, \"credit\": {...}}",
        agent=data_analyst,
    )

    assess_risk_task = Task(
        description=(
            "From task context, read borrower annual_income and monthly_debt, and credit "
            "fico_score. Call calculate_dti and check_fico. Return strict JSON with keys: "
            "dti_result, fico_result, recommendation where recommendation is APPROVE or "
            "MANUAL_REVIEW."
        ),
        expected_output=(
            "Strict JSON object: {\"dti_result\": {...}, \"fico_result\": {...}, "
            "\"recommendation\": \"APPROVE|MANUAL_REVIEW\"}"
        ),
        agent=risk_assessor,
        context=[fetch_data_task],
    )

    crew = Crew(
        agents=[data_analyst, risk_assessor],
        tasks=[fetch_data_task, assess_risk_task],
        process=Process.sequential,
        verbose=False,
    )

    return crew, fetch_data_task, assess_risk_task


def _normalize_payload(value: Any) -> Any:
    if isinstance(value, str):
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return {"raw": value}
    return value


def _deterministic_fallback(app_id: str) -> dict[str, Any]:
    borrower = lc_pull_borrower_data.invoke({"app_id": app_id})
    ssn_last_four = borrower.get("ssn_last_four", "")
    credit = lc_pull_credit_report.invoke({"ssn_last_four": ssn_last_four})

    dti_result = lc_calculate_dti.invoke(
        {
            "annual_income": borrower.get("annual_income", 0),
            "monthly_debt": borrower.get("monthly_debt", 0),
        }
    )
    fico_result = lc_check_fico_eligibility.invoke(
        {"fico_score": credit.get("fico_score", 0)}
    )

    recommendation = "APPROVE"
    if (not dti_result.get("pass", False)) or (not fico_result.get("eligible", False)):
        recommendation = "MANUAL_REVIEW"

    return {
        "task_1": {"borrower": borrower, "credit": credit},
        "task_2": {
            "dti_result": dti_result,
            "fico_result": fico_result,
            "recommendation": recommendation,
            "context": "Task 1",
        },
        "run_mode": "deterministic-fallback",
    }


def run_crew(app_id: str = "APP-001", print_output: bool = True) -> dict[str, Any]:
    """Run the 2-agent CrewAI flow and print results.

    If live CrewAI model execution is unavailable (for example no API key),
    fall back to deterministic tool orchestration so the exercise still runs.
    """

    try:
        crew, fetch_data_task, assess_risk_task = _build_crew()
        crew_output = crew.kickoff(inputs={"app_id": app_id})

        task_1_output = _normalize_payload(fetch_data_task.output.raw if fetch_data_task.output else None)
        task_2_output = _normalize_payload(assess_risk_task.output.raw if assess_risk_task.output else None)

        result: dict[str, Any] = {
            "task_1": task_1_output,
            "task_2": task_2_output,
            "run_mode": "crewai-live",
            "crew_raw": str(crew_output),
        }
    except Exception as exc:  # pragma: no cover - exercised only when live kickoff fails
        result = _deterministic_fallback(app_id)
        result["crewai_error"] = str(exc)

    if print_output:
        print("Data Analyst Results:")
        print(json.dumps(result.get("task_1"), indent=2, sort_keys=True))
        print("Risk Assessor Results:")
        print(json.dumps(result.get("task_2"), indent=2, sort_keys=True))
        print(f"Run mode: {result.get('run_mode')}")
        if result.get("crewai_error"):
            print(f"CrewAI fallback reason: {result['crewai_error']}")

    return result


if __name__ == "__main__":
    run_crew()

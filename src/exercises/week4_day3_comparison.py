"""Week 4 Day 3: CrewAI vs LangGraph side-by-side comparison."""

from __future__ import annotations

import inspect
import time
from typing import Any, TypedDict

from langgraph.graph import END, START, StateGraph

from src.exercises.week4_day3_crewai import run_crew
from src.tools.fetch_tools import pull_borrower_data
from src.tools.fetch_tools import pull_credit_report
from src.tools.underwriting_tools import calculate_dti
from src.tools.underwriting_tools import check_fico_eligibility


class UnderwritingState(TypedDict, total=False):
    borrower: dict[str, Any]
    credit: dict[str, Any]
    risk: dict[str, Any]


def run_langgraph(app_id: str = "APP-001") -> dict[str, Any]:
    """Solve fetch-data -> risk-assessment with LangGraph."""

    def fetch_data_node(state: UnderwritingState) -> UnderwritingState:
        borrower = pull_borrower_data.invoke({"app_id": app_id})
        ssn_last_four = borrower.get("ssn_last_four", "")
        credit = pull_credit_report.invoke({"ssn_last_four": ssn_last_four})
        return {"borrower": borrower, "credit": credit}

    def assess_risk_node(state: UnderwritingState) -> UnderwritingState:
        borrower = state["borrower"]
        credit = state["credit"]

        dti_result = calculate_dti.invoke(
            {
                "annual_income": borrower.get("annual_income", 0),
                "monthly_debt": borrower.get("monthly_debt", 0),
            }
        )
        fico_result = check_fico_eligibility.invoke(
            {"fico_score": credit.get("fico_score", 0)}
        )

        recommendation = "APPROVE"
        if (not dti_result.get("pass", False)) or (not fico_result.get("eligible", False)):
            recommendation = "MANUAL_REVIEW"

        return {
            "risk": {
                "dti_result": dti_result,
                "fico_result": fico_result,
                "recommendation": recommendation,
            }
        }

    graph = StateGraph(UnderwritingState)
    graph.add_node("fetch_data", fetch_data_node)
    graph.add_node("assess_risk", assess_risk_node)
    graph.add_edge(START, "fetch_data")
    graph.add_edge("fetch_data", "assess_risk")
    graph.add_edge("assess_risk", END)

    app = graph.compile()
    return app.invoke({})


def _effective_loc(func: Any) -> int:
    lines = inspect.getsource(func).splitlines()
    return sum(1 for line in lines if line.strip() and not line.strip().startswith("#"))


def _quality_score(output: dict[str, Any]) -> int:
    """Simple structure score for this exercise (0 to 5)."""
    score = 0
    if isinstance(output, dict):
        score += 1
    if "borrower" in output and "credit" in output:
        score += 2
    if "risk" in output and output["risk"].get("recommendation"):
        score += 2
    return score


def run_comparison(app_id: str = "APP-001") -> dict[str, Any]:
    """Run and print CrewAI vs LangGraph comparison summary."""

    t0 = time.perf_counter()
    crew_result = run_crew(app_id=app_id, print_output=False)
    crew_elapsed = time.perf_counter() - t0
    crew_normalized = {
        "borrower": crew_result.get("task_1", {}).get("borrower", {}),
        "credit": crew_result.get("task_1", {}).get("credit", {}),
        "risk": crew_result.get("task_2", {}),
    }

    t1 = time.perf_counter()
    langgraph_result = run_langgraph(app_id=app_id)
    langgraph_elapsed = time.perf_counter() - t1

    crew_loc = _effective_loc(run_crew)
    langgraph_loc = _effective_loc(run_langgraph)
    crew_quality = _quality_score(crew_normalized)
    langgraph_quality = _quality_score(langgraph_result)

    easier_to_write = "CrewAI"
    more_structured = "LangGraph"

    summary = {
        "crewai": {
            "loc": crew_loc,
            "execution_seconds": crew_elapsed,
            "quality_score": crew_quality,
            "run_mode": crew_result.get("run_mode"),
        },
        "langgraph": {
            "loc": langgraph_loc,
            "execution_seconds": langgraph_elapsed,
            "quality_score": langgraph_quality,
        },
        "observation": {
            "easier_to_write": easier_to_write,
            "more_structured_output": more_structured,
        },
    }

    print("=== CrewAI vs LangGraph (Same Problem) ===")
    print(f"CrewAI LOC: {crew_loc}")
    print(f"LangGraph LOC: {langgraph_loc}")
    print(f"CrewAI execution time: {crew_elapsed:.6f}s")
    print(f"LangGraph execution time: {langgraph_elapsed:.6f}s")
    print(f"CrewAI output quality score: {crew_quality}/5")
    print(f"LangGraph output quality score: {langgraph_quality}/5")
    print(f"Easier to write: {easier_to_write}")
    print(f"More structured output: {more_structured}")

    return summary


if __name__ == "__main__":
    run_comparison()

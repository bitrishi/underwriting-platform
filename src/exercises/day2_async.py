"""Day 2: Async Orchestrator Exercise - Simulating multi-agent loan underwriting workflow"""

import asyncio
import time
from typing import Any


class OrchestrationMetrics:
    """Track timing metrics for orchestration steps."""
    
    def __init__(self):
        self.start_time = time.time()
        self.steps = []
    
    def record_step(self, step_name: str, elapsed: float) -> None:
        """Record completion of a step."""
        self.steps.append({"name": step_name, "elapsed": elapsed})
        print(f"  ✓ {step_name}: {elapsed:.2f}s")
    
    def total_time(self) -> float:
        """Get total elapsed time."""
        return time.time() - self.start_time
    
    def print_summary(self) -> None:
        """Print orchestration summary."""
        print(f"\n📊 Orchestration Summary:")
        print(f"  Total Time: {self.total_time():.2f}s")
        for step in self.steps:
            print(f"    - {step['name']}: {step['elapsed']:.2f}s")


# Semaphore to limit concurrent Bedrock API calls to 2
bedrock_semaphore = asyncio.Semaphore(2)


async def fetch_data(
    borrower_id: str,
    metrics: OrchestrationMetrics,
) -> dict[str, Any]:
    """
    Fetch borrower data from external systems (credit bureau, employment, income).
    This is a blocking operation that must complete before other agents run.
    
    Simulates: API call to credit bureau, employment verification, income verification
    Duration: 2 seconds (slower - multiple external calls)
    
    Args:
        borrower_id: Borrower identifier
        metrics: Metrics tracker
        
    Returns:
        Dictionary with fetched data
    """
    async with bedrock_semaphore:
        step_start = time.time()
        print(f"[fetch_data] Gathering borrower {borrower_id} data...")
        await asyncio.sleep(2.0)  # Simulate 2s API latency
        
        data = {
            "borrower_id": borrower_id,
            "fico_score": 750,
            "annual_income": 120000,
            "employment_status": "employed",
            "existing_debt": 2000,
        }
        
        elapsed = time.time() - step_start
        metrics.record_step("fetch_data", elapsed)
        return data


async def review_docs(
    borrower_id: str,
    fetched_data: dict[str, Any],
    metrics: OrchestrationMetrics,
) -> dict[str, Any]:
    """
    Review and analyze borrower documents (income verification, tax returns, etc.).
    Depends on fetch_data output. Runs concurrently with other agents.
    
    Duration: 1.5 seconds (moderate - document processing)
    
    Args:
        borrower_id: Borrower identifier
        fetched_data: Output from fetch_data()
        metrics: Metrics tracker
        
    Returns:
        Dictionary with document review results
    """
    async with bedrock_semaphore:
        step_start = time.time()
        print(f"[review_docs] Analyzing documents for {borrower_id}...")
        await asyncio.sleep(1.5)  # Simulate 1.5s processing
        
        results = {
            "borrower_id": borrower_id,
            "documents_valid": True,
            "income_verified": fetched_data["annual_income"],
            "document_quality": "excellent",
        }
        
        elapsed = time.time() - step_start
        metrics.record_step("review_docs", elapsed)
        return results


async def score_risk(
    borrower_id: str,
    fetched_data: dict[str, Any],
    metrics: OrchestrationMetrics,
) -> dict[str, Any]:
    """
    Calculate credit risk score based on borrower data.
    Depends on fetch_data output. Runs concurrently with other agents.
    
    Duration: 1.0 second (fast - numerical calculation)
    
    Args:
        borrower_id: Borrower identifier
        fetched_data: Output from fetch_data()
        metrics: Metrics tracker
        
    Returns:
        Dictionary with risk score
    """
    async with bedrock_semaphore:
        step_start = time.time()
        print(f"[score_risk] Computing risk score for {borrower_id}...")
        await asyncio.sleep(1.0)  # Simulate 1s processing
        
        # Simple risk scoring
        fico = fetched_data["fico_score"]
        dti = fetched_data["existing_debt"] / (fetched_data["annual_income"] / 12)
        risk_score = (fico / 850.0) * 100 - (dti * 20)
        
        results = {
            "borrower_id": borrower_id,
            "risk_score": max(0, min(100, risk_score)),
            "risk_level": "low" if risk_score > 70 else "medium" if risk_score > 50 else "high",
            "dti_ratio": dti,
        }
        
        elapsed = time.time() - step_start
        metrics.record_step("score_risk", elapsed)
        return results


async def check_compliance(
    borrower_id: str,
    fetched_data: dict[str, Any],
    metrics: OrchestrationMetrics,
) -> dict[str, Any]:
    """
    Check regulatory compliance (KYC, AML, sanctions lists).
    Depends on fetch_data output. Runs concurrently with other agents.
    
    Duration: 0.8 seconds (fast - database lookups)
    
    Args:
        borrower_id: Borrower identifier
        fetched_data: Output from fetch_data()
        metrics: Metrics tracker
        
    Returns:
        Dictionary with compliance results
    """
    async with bedrock_semaphore:
        step_start = time.time()
        print(f"[check_compliance] Verifying compliance for {borrower_id}...")
        await asyncio.sleep(0.8)  # Simulate 0.8s processing
        
        results = {
            "borrower_id": borrower_id,
            "kyc_passed": True,
            "aml_passed": True,
            "sanctions_check": "clear",
            "compliance_status": "approved",
        }
        
        elapsed = time.time() - step_start
        metrics.record_step("check_compliance", elapsed)
        return results


async def orchestrate(borrower_id: str) -> dict[str, Any]:
    """
    Orchestrate the loan underwriting workflow.
    
    Flow:
    1. Fetch data (blocking - takes 2s)
    2. Run 3 agents concurrently (takes ~1.5s max):
       - review_docs (1.5s)
       - score_risk (1.0s)
       - check_compliance (0.8s)
    
    Total expected time: ~3.5s (not 2+1.5+1+0.8=5.3s sequentially)
    Semaphore limits concurrent Bedrock calls to 2, so actual timing:
    - fetch_data: 2s (uses 1 semaphore slot)
    - Then: review_docs (1.5s) + score_risk can start (1.0s with other slot)
    - Then: check_compliance (0.8s)
    So: 2 + max(1.5, 1.0) + 0.8 = ~4.3s with semaphore constraint
    
    Args:
        borrower_id: Borrower identifier
        
    Returns:
        Final underwriting decision
    """
    metrics = OrchestrationMetrics()
    
    print(f"\n🚀 Starting underwriting orchestration for {borrower_id}")
    print("=" * 60)
    
    # Step 1: Fetch data (must complete first)
    print("\n📥 Phase 1: Fetching Data (Sequential)")
    fetched_data = await fetch_data(borrower_id, metrics)
    
    # Step 2: Run remaining agents concurrently
    print(f"\n⚡ Phase 2: Running Agents Concurrently")
    print(f"   (Semaphore limits to 2 concurrent Bedrock calls)")
    
    concurrent_results = await asyncio.gather(
        review_docs(borrower_id, fetched_data, metrics),
        score_risk(borrower_id, fetched_data, metrics),
        check_compliance(borrower_id, fetched_data, metrics),
    )
    
    review_result, risk_result, compliance_result = concurrent_results
    
    # Compile final decision
    final_decision = {
        "borrower_id": borrower_id,
        "fetched_data": fetched_data,
        "review_docs": review_result,
        "risk_score": risk_result,
        "compliance": compliance_result,
        "final_decision": "APPROVED" if (
            risk_result["risk_level"] in ["low", "medium"] and
            compliance_result["compliance_status"] == "approved"
        ) else "REQUIRES_REVIEW",
    }
    
    metrics.print_summary()
    print("=" * 60)
    
    return final_decision


async def main() -> None:
    """Run the orchestration example."""
    decision = await orchestrate("BORROWER_12345")
    
    print(f"\n📋 Final Decision: {decision['final_decision']}")
    print(f"   Risk Level: {decision['risk_score']['risk_level']}")
    print(f"   Compliance: {decision['compliance']['compliance_status']}")


if __name__ == "__main__":
    asyncio.run(main())

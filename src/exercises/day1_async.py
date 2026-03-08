"""Day 1: Async/Await Exercise - Concurrent API calls using asyncio.gather"""

import asyncio
import time
from typing import Any


async def simulate_api_call(call_id: int, delay: float = 1.0) -> dict[str, Any]:
    """
    Simulate an async API call that takes a specified delay.
    
    Args:
        call_id: Identifier for this API call
        delay: Time to simulate (in seconds)
        
    Returns:
        Dictionary with call results
    """
    print(f"  [Call {call_id}] Starting...")
    await asyncio.sleep(delay)
    print(f"  [Call {call_id}] Completed")
    return {
        "call_id": call_id,
        "status": "success",
        "delay": delay,
        "timestamp": time.time()
    }


async def fetch_concurrent_data() -> list[dict[str, Any]]:
    """
    Fetch data from 3 concurrent API calls using asyncio.gather.
    
    Each call simulates a 1-second API request. When run concurrently,
    all 3 should complete in ~1 second total, not 3 seconds.
    
    Returns:
        List of results from all API calls
    """
    print("Starting 3 concurrent API calls...")
    start_time = time.time()
    
    # Create 3 concurrent tasks
    results = await asyncio.gather(
        simulate_api_call(1, delay=1.0),
        simulate_api_call(2, delay=1.0),
        simulate_api_call(3, delay=1.0),
    )
    
    elapsed_time = time.time() - start_time
    print(f"\n✅ All calls completed in {elapsed_time:.2f} seconds")
    print(f"   (Sequential would take ~3.0 seconds)")
    
    return results


async def main() -> None:
    """Run the concurrent API calls example."""
    results = await fetch_concurrent_data()
    
    print("\nResults:")
    for result in results:
        print(f"  Call {result['call_id']}: {result['status']}")


if __name__ == "__main__":
    asyncio.run(main())

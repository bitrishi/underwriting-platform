import time
import random
from langchain_core.runnables import RunnableParallel, RunnableLambda


def credit_check(input_data):
    """Simulate a credit check lookup."""
    sleep_time = random.uniform(1, 3)  # Random sleep between 1-3 seconds
    time.sleep(sleep_time)
    credit_score = random.randint(300, 850)
    return {"credit_score": credit_score, "lookup_time": sleep_time}


def employment_check(input_data):
    """Simulate an employment check lookup."""
    sleep_time = random.uniform(1, 3)
    time.sleep(sleep_time)
    statuses = ["employed", "unemployed", "self-employed", "retired"]
    status = random.choice(statuses)
    return {"employment_status": status, "lookup_time": sleep_time}


def property_check(input_data):
    """Simulate a property check lookup."""
    sleep_time = random.uniform(1, 3)
    time.sleep(sleep_time)
    property_value = random.randint(100000, 1000000)
    return {"property_value": property_value, "lookup_time": sleep_time}


# Create RunnableLambda chains
credit_chain = RunnableLambda(credit_check)
employment_chain = RunnableLambda(employment_check)
property_chain = RunnableLambda(property_check)

# Create RunnableParallel to run them in parallel
parallel_chains = RunnableParallel(
    credit=credit_chain,
    employment=employment_chain,
    property=property_chain
)

# Sequential execution for comparison
def run_sequential():
    start_time = time.time()
    credit_result = credit_check({})
    employment_result = employment_check({})
    property_result = property_check({})
    end_time = time.time()
    return {
        "credit": credit_result,
        "employment": employment_result,
        "property": property_result,
        "total_time": end_time - start_time
    }

if __name__ == "__main__":
    print("Starting script")
    print("Running chains in parallel...")
    start_time = time.time()
    parallel_results = parallel_chains.invoke({})
    end_time = time.time()
    parallel_total_time = end_time - start_time

    print("Parallel Results:")
    for key, result in parallel_results.items():
        print(f"  {key}: {result}")

    print(".2f")

    print("\nRunning chains sequentially for comparison...")
    sequential_results = run_sequential()
    sequential_total_time = sequential_results["total_time"]

    print("Sequential Results:")
    for key, result in sequential_results.items():
        if key != "total_time":
            print(f"  {key}: {result}")

    print(".2f")

    # Verify concurrency: parallel time should be roughly the max of individual times
    max_individual_time = max(
        parallel_results["credit"]["lookup_time"],
        parallel_results["employment"]["lookup_time"],
        parallel_results["property"]["lookup_time"]
    )
    print(".2f")
    print(".2f")
    print(".2f")
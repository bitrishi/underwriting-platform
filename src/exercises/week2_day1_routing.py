from langchain_core.runnables import RunnableBranch, RunnableLambda


def fast_approve(input_data):
    """Handle fast approval for high FICO scores."""
    return {"decision": "FAST_APPROVED", "message": "Application fast-tracked for approval due to excellent credit score."}


def standard_review(input_data):
    """Handle standard review for medium FICO scores."""
    return {"decision": "STANDARD_REVIEW", "message": "Application requires standard underwriting review."}


def auto_deny(input_data):
    """Handle auto-deny for low FICO scores."""
    return {"decision": "AUTO_DENIED", "message": "Application automatically denied due to insufficient credit score."}


# Create RunnableLambda chains
fast_approve_chain = RunnableLambda(fast_approve)
standard_review_chain = RunnableLambda(standard_review)
auto_deny_chain = RunnableLambda(auto_deny)

# Define routing conditions
def route_to_fast_approve(input_data):
    """Route to fast approve if FICO > 750."""
    return input_data.get("fico_score", 0) > 750

def route_to_standard_review(input_data):
    """Route to standard review if FICO 680-750."""
    fico = input_data.get("fico_score", 0)
    return 680 <= fico <= 750

def route_to_auto_deny(input_data):
    """Route to auto deny if FICO < 680."""
    return input_data.get("fico_score", 0) < 680

# Create RunnableBranch for routing
routing_chain = RunnableBranch(
    (route_to_fast_approve, fast_approve_chain),
    (route_to_standard_review, standard_review_chain),
    auto_deny_chain  # default case
)


if __name__ == "__main__":
    # Test cases with different FICO scores
    test_cases = [
        {"fico_score": 800},  # Should fast approve
        {"fico_score": 720},  # Should standard review
        {"fico_score": 650},  # Should auto deny
        {"fico_score": 750},  # Should standard review (boundary)
        {"fico_score": 680},  # Should standard review (boundary)
        {"fico_score": 751},  # Should fast approve (boundary)
        {"fico_score": 679},  # Should auto deny (boundary)
    ]

    print("Testing RunnableBranch routing with different FICO scores:")
    print("=" * 60)

    for test_case in test_cases:
        result = routing_chain.invoke(test_case)
        print(f"FICO Score: {test_case['fico_score']}")
        print(f"Decision: {result['decision']}")
        print(f"Message: {result['message']}")
        print("-" * 40)
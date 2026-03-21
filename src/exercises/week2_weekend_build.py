from src.agents.fetch_data import create_fetch_data_agent
from src.callbacks.tracer import UnderwritingTracer


def extract_agent_text(result: dict) -> str:
    """Extract readable text output from create_agent state payload."""
    messages = result.get("messages", [])
    if messages:
        last = messages[-1]
        content = getattr(last, "content", str(last))
        if isinstance(content, list):
            return "\n".join(str(item) for item in content)
        return str(content)

    return str(result)


def main():
    agent = create_fetch_data_agent()
    tracer = UnderwritingTracer()
    
    # Test with two applications
    for app_id in ["APP-001", "APP-002"]:
        print(f"\n{'='*60}")
        print(f"  Fetching data for {app_id}")
        print(f"{'='*60}\n")
        
        result = agent.invoke(
            {
                "messages": [
                    {
                        "role": "user",
                        "content": f"Gather all underwriting data for application {app_id}",
                    }
                ]
            },
            config={"callbacks": [tracer]},
        )
        
        print(f"\n{'='*60}")
        print(f"  RESULT")
        print(f"{'='*60}")
        print(extract_agent_text(result))
        
        print(f"\n  Trace: {len(tracer.trace)} actions recorded")
        print(tracer.get_trace_summary())
        
        tracer.trace = []  # reset for next application


if __name__ == "__main__":
    main()
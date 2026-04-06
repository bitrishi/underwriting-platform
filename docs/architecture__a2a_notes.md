# A2A Specification Notes

Source reviewed: `https://google.github.io/A2A/` (redirected to `a2aproject.github.io/A2A` / `a2a-protocol.org`) and the A2A specification overview.

## Three Key Takeaways

1. A2A standardizes agent-to-agent interoperability while preserving opaque execution.
- A2A clients and remote agent servers can collaborate across frameworks/vendors.
- Agents exchange capabilities and results without exposing internal memory, plans, or tool internals.
- This is directly useful when organizations need cross-boundary delegation between independently owned agent systems.

2. The protocol is task-centric and async-first by design.
- Long-running work is modeled as `Task` objects with lifecycle states and task IDs.
- A2A supports multiple update patterns: polling (`getTask`), streaming (SSE events), and push notifications (webhooks).
- The model is built for multi-turn and human-in-the-loop workflows, not only single request/response calls.

3. Discovery + security are first-class via Agent Cards and web-native auth.
- An Agent Card advertises identity, endpoint, skills/capabilities, and required security schemes.
- A2A relies on established web standards (HTTP(S), JSON-RPC, OAuth/OpenID and related HTTP auth patterns).
- This makes A2A enterprise-friendly for governance, access control, and service onboarding.

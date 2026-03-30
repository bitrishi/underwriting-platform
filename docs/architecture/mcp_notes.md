# MCP Specification Notes

Source reviewed: `https://modelcontextprotocol.io` (overview + architecture sections).

## Three Key Takeaways

1. MCP standardizes AI-to-tool integration with explicit roles.
- The protocol separates participants into host, client, and server.
- Hosts can connect to many servers by creating one client session per server.
- This supports modular integration without rewriting agent logic per backend.

2. MCP has a two-layer model that cleanly separates semantics from transport.
- Data layer: JSON-RPC 2.0 methods for lifecycle, discovery, and execution.
- Transport layer: `stdio` for local execution and streamable HTTP for remote setups.
- Same protocol messages can move across either transport, reducing migration friction.

3. Discovery and capability negotiation are first-class protocol features.
- Sessions start with `initialize` and capability negotiation (protocol version + supported primitives).
- Tools are discovered via `tools/list` before invocation via `tools/call`.
- Tool contracts use JSON Schema (`inputSchema`), enabling strong validation and dynamic tool catalogs.

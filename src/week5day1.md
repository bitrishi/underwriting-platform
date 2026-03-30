md_content = """# Week 5, Day 1: MCP — Model Context Protocol

## Session Overview
**Date:** Week 5, Day 1
**Topic:** MCP (Model Context Protocol) — standardized tool connectivity for AI agents, the protocol format, when it provides real value vs when @tool wrappers are sufficient, and honest evaluation of MCP for your underwriting system.
**Prerequisites:** Week 4 complete orchestrator with @tool-based tools

---

## 1. What Problem MCP Solves

### 1.1 The Current Situation

Every tool in your system is a Python function you wrote and deployed alongside your agent code. pull_borrower_data is YOUR function calling YOUR API. calculate_dti is YOUR function with YOUR formula. search_lending_policies is YOUR function querying YOUR vector store.

This works when you control everything. The problem emerges when integrating with systems you do NOT control — credit bureau APIs, property valuation services, employment verification, GSE systems. Each has its own API format, authentication method, error structure, and data conventions. Writing custom @tool wrappers for each is manageable at 3-4 integrations but becomes engineering burden at 20+.

### 1.2 What MCP Does

MCP standardizes how AI agents connect to external tools and data sources. Instead of custom wrappers per system, providers publish MCP servers exposing capabilities in a standard format. Any MCP client connects to any MCP server using the same protocol.

The standardization is the value — not any single technical capability. Like REST standardized web APIs and JDBC standardized database access, MCP standardizes AI agent tool access.

---

## 2. The JDBC Analogy

Before JDBC, every database needed a custom driver with its own API. Oracle was different from MySQL was different from PostgreSQL. JDBC standardized the interface — you write against the JDBC API, the driver handles specifics. Switch databases by changing the connection URL, not the application code.

MCP is JDBC for AI agent tools. JDBC driver maps to MCP server. JDBC connection maps to MCP client session. DatabaseMetaData.getTables() maps to MCP capability discovery (tools/list). PreparedStatement maps to tool call (tools/call). ResultSet maps to tool result.

Write against the standard interface. Provider implements specifics behind it. Switch providers by changing the server URL, not the agent code.

---

## 3. How MCP Works

### 3.1 Three Components

The MCP Server is published by the tool provider (or by you, wrapping an internal system). It exposes capabilities and runs as a separate process — local, remote, or cloud-managed.

The MCP Client is built into your agent framework. LangChain has MCP integration. It connects to servers, discovers capabilities, and makes tool calls through the standard protocol.

The MCP Protocol is JSON-RPC over stdio (local) or HTTP/SSE (remote). Defines standard message formats for capability discovery and tool invocation.

### 3.2 Three Capability Types

Tools are functions the agent can call — same concept as @tool but via standard protocol. Resources are data the agent can browse — like a file system or database. Prompts are pre-built templates the server provides — optimized for its domain.

---

## 4. The Protocol Format

### 4.1 Discovery: tools/list

The client sends a JSON-RPC request with method "tools/list". The server responds with an array of tool definitions, each containing name, description, and inputSchema (using JSON Schema format — the same format that LangChain @tool and Pydantic use).

This happens ONCE at startup, not per call. The tool list is cached. The agent discovers on next restart if the server adds new tools.

### 4.2 Invocation: tools/call

The client sends a JSON-RPC request with method "tools/call", including the tool name and arguments. The server executes and returns the result in a standard content format.

Two message types cover 90% of MCP usage. The simplicity is deliberate — easy for every client and server to implement.

### 4.3 Why JSON-RPC + JSON Schema

JSON-RPC for transport: every message has method, params, and ID. Simpler than REST (no URL design, HTTP method selection, content negotiation). One endpoint, one format.

JSON Schema for tool definitions: the same standard used by OpenAPI/Swagger, Pydantic, and LangChain. MCP tool schemas go DIRECTLY into the LLM prompt as tool definitions with zero translation. The LLM cannot tell whether a tool came from a local @tool function or an MCP server — both produce identical JSON Schema.

---

## 5. What Changes in Your Agent Code

### 5.1 Without MCP (Today)

You import tool functions from your local codebase, list them explicitly, and pass to the agent. You decide at DEVELOPMENT TIME which tools the agent has. The list is static — changing it requires code change and redeployment.

### 5.2 With MCP

You configure MCP server URLs. At startup, the MCP client connects to each server, calls tools/list to discover available tools, and converts the schemas into LangChain tool objects. The agent receives these tools identically to how it receives @tool functions. The LLM prompt looks the same either way.

The difference: tools come from remote servers instead of local imports. Adding a tool on the server means the agent discovers it on next restart without any code change.

### 5.3 Multiple Agents, Multiple Servers

You configure each agent with the servers relevant to its domain — same way you currently assign tools. FetchData connects to data-related MCP servers. Compliance connects to policy-related MCP servers. YOU still control which agent gets which tools. MCP does not change your multi-agent architecture.

You can also filter which tools to pull from a server, preventing tool count explosion. Your 4-8 tools per agent design remains the same.

---

## 6. MCP Security

Authentication happens between YOUR CODE (MCP client) and the MCP server. The LLM never sees credentials. Identical to how your current @tool functions handle auth internally.

MCP supports OAuth 2.0, API keys, and mutual TLS. For Goldman internal servers, use existing PingFederate tokens. For external servers, auth configured on the client connection.

Authorization controlled by the server — your agent can pull reports but not modify records. Data isolation per connection. Audit on both sides — every tool call logged with identity, parameters, timestamp, response.

---

## 7. The Real Value: Standard Format Enables Config-Only Switching

### 7.1 Without MCP: Every API Is Different

Three credit providers have three different URL structures, three different auth methods (Bearer, Basic, API key), three different request formats (JSON, XML, query params), three different response schemas, and two different content types. Switching providers means rewriting the wrapper.

### 7.2 With MCP: Every Server Speaks the Same Language

All three providers publish MCP servers. Your agent talks to any of them with identical code: same tools/list call, same tools/call format, same response structure. Switching providers means changing ONE server URL in configuration. Zero code changes.

THIS is the real value. Not that MCP is better than REST for any single integration. But that 100 different providers all speaking the same format means your client code is written ONCE and works with ALL of them.

### 7.3 The Condition for Config-Only Switching

Switching is truly config-only WHEN the MCP servers agree on tool names and response schemas. If Equifax MCP exposes pull_credit_report returning fico:740 and TransUnion MCP exposes pull_credit_report returning fico:745 — config change only. If they use different tool names and schemas — agent code must still change.

This is why industry standardization matters. If the mortgage industry agrees on standard MCP tool names and schemas, switching between any provider is config change. Without that agreement, the protocol is standard but the semantics differ.

JDBC succeeded because SQL was already standardized. MCP will succeed fully when tool schemas are standardized per industry.

---

## 8. Honest Evaluation: MCP for Your System

### 8.1 Claimed Advantages Evaluated

Automatic tool discovery — real but trivial. Saves writing import lines. You add tools maybe once a month.

Standard schema format — you already solve this with @tool. LangChain standardizes on your side. No net gain unless someone ELSE maintains the MCP server.

Vendor switching — you can do the same today by changing @tool internals and redeploying. MCP moves the change to the server. Same total work when you own both sides.

Multi-team sharing — real advantage at organizational scale. If 20 Goldman teams need Camelot data, one MCP server is better than 20 custom wrappers. But Goldman already has microservices for this — each team calls the same REST API and writes a thin @tool wrapper (5-10 lines). MCP eliminates those thin wrappers.

Third-party marketplace — potentially significant in 2-3 years when credit bureaus and GSEs publish MCP servers. Zero value today since none exist.

### 8.2 The Honest Bottom Line

For YOUR current underwriting system: MCP provides almost no practical advantage over @tool wrappers. You control your tools, have 4 focused agents, tools are stable.

For Goldman's AI PLATFORM in a year: if 10+ teams build agents needing the same data sources, MCP becomes the standard interface preventing redundant integration work.

For the mortgage industry in 2-3 years: when providers publish MCP servers, connecting to a credit bureau becomes config instead of a multi-day integration.

### 8.3 Recommendation

Understand MCP (you now do). Build with @tool today. Document when Goldman should adopt MCP and the migration path. Do not implement MCP for your underwriting system — it adds complexity without current benefit.

---

## 9. MCP vs Microservice: The Comparison

### 9.1 It IS Like a Microservice

MCP server is essentially a microservice with a standardized contract. Your Camelot architecture already does this — Angular UI calls Core Service REST API. Switch DocumentDB to PostgreSQL, UI unchanged because the API contract stays the same.

MCP is the same for AI tools. Agent calls MCP server. Switch Equifax to TransUnion internally. Agent unchanged because the MCP contract stays the same.

### 9.2 The Adapter Pattern from Java

The parallel is exact. Java's CreditService interface with EquifaxAdapter and TransUnionAdapter implementations. Your service uses the interface, Spring injects the right adapter, switch in config. MCP server is the adapter. MCP protocol is the interface. Switch implementations on the server side, agent code unchanged.

### 9.3 What MCP Adds Beyond a Regular Microservice

Runtime capability discovery (agent asks "what tools do you have?" — like reflection). Standardized tool schema compatible with LLM prompt format. These are incremental improvements over REST, not revolutionary. If REST had been designed specifically for AI tool calling, it would look like MCP.

---

## 10. Q&A

### Q: Today I write @tool wrappers for Goldman's existing microservices. If they exposed MCP instead, what is the gain?

Except for automatic tool discovery, the gain is minimal when you are the only consumer. The real value emerges when multiple teams consume the same tools — MCP eliminates per-team wrapper code. For your single underwriting system, @tool is correct.

### Q: How do I tell agents to connect to multiple MCP servers?

Same way you assign tools today — configure each agent with relevant server URLs. FetchData connects to data servers, Compliance to policy servers. You control assignment. MCP does not change your multi-agent architecture.

### Q: Will MCP increase tools per agent?

Not if you configure correctly. You can filter which tools to pull from each server. Your 4-8 tools per agent design stays the same.

### Q: How does authentication work?

Between YOUR code (MCP client) and the server. LLM never sees credentials. Same as your current @tool functions handling auth internally. MCP supports OAuth, API keys, mTLS.

### Q: Why is MCP needed? What was wrong with passing tools?

Nothing is wrong with @tool for your case. MCP solves organizational scale — multiple teams sharing tools, third-party provider standardization, runtime discovery. These are not your problems today.

### Q: Is the protocol just REST?

Similar but adds: runtime capability discovery (tools/list), standardized tool schema (JSON Schema matching LangChain format), bidirectional communication (server push). If REST was designed for AI tools, it would look like MCP.

### Q: For credit scores from multiple vendors, does MCP help choose?

No. MCP is connectivity, not decision-making. It connects you to vendors but does not choose between them. Vendor routing logic is YOUR code. MCP just ensures the connection format is standard across all vendors.

### Q: Goldman has microservices with APIs. I write @tool wrappers. If they expose MCP instead, what changes?

You eliminate the thin @tool wrapper (5-10 lines per tool). The MCP client auto-discovers tools from the server. The gain is real but small for a single consuming team. It becomes significant when 20 teams consume the same services.

### Q: The real value is when format is standard and switching is config change?

Exactly. ONE client works with ANY server. Switch providers by changing URL. Add providers by connecting to new server. This value is zero with 1 provider per tool type. It becomes significant at organizational scale with 50+ tool providers where custom integration per provider creates massive maintenance burden.

### Q: So it is like a microservice with standardized contract, and switching vendors is just changing the MCP server?

Exactly. The MCP server is the abstraction layer. Vendor changes behind it. Agent unchanged. The Adapter pattern from Java. The condition: MCP servers must agree on tool names and response schemas. If Equifax and TransUnion expose the same pull_credit_report schema — true config switch. If schemas differ — still need mapping.

---

## 11. Summary

| Concept | What It Does | Analogy |
|---------|-------------|---------|
| MCP | Standardizes agent-to-tool communication | JDBC for AI tools |
| MCP Server | Exposes tools via standard protocol | JDBC driver / microservice |
| MCP Client | Connects and discovers tools | JDBC Connection |
| tools/list | Runtime capability discovery | DatabaseMetaData.getTables() |
| tools/call | Standard tool invocation | PreparedStatement.execute() |
| JSON Schema | Tool parameter definitions | Same as Pydantic / OpenAPI |
| @tool vs MCP | Direct wrapper vs protocol-based | Direct SQL vs JDBC |
| Config-only switching | Change server URL to switch providers | Change JDBC connection string |
| The real value | Standard format across ALL providers | SQL standard across ALL databases |
| Current recommendation | Use @tool, adopt MCP at organizational scale | Use direct calls, adopt JDBC when scaling |
"""

with open("week5_day1.md", "w") as f:
    f.write(md_content)
print(f"✅ MD: {len(md_content)} chars")
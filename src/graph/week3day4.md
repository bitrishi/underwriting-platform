# Week 3 — Day 4: Knowledge Graphs with Neo4j

**Date:** Session 14  
**Duration:** 30 minutes theory + assignment  
**Status:** ✅ Complete (all 5 components working)

---

## 1. What Is a Knowledge Graph?

A knowledge graph stores data as **nodes** (entities/things) and **edges** (relationships/connections between things). Each node and edge can have **properties** (key-value metadata).

This is fundamentally different from how relational databases (MySQL, PostgreSQL) or document databases (MongoDB) store data. In those systems, data lives in rows/documents, and connections between data are expressed through foreign keys or embedded documents that require JOIN operations or lookups to traverse. In a graph database, the connections ARE the data — stored as first-class citizens with direct physical pointers.

### Graph vs. Relational vs. Document — Same Data, Three Models

Consider this underwriting scenario: John Doe works at TechCorp, which is in the Technology industry. John applied for a loan secured by a property in Texas.

**Relational (MySQL) — 6 tables, foreign keys:**
```
Table: borrowers         Table: companies          Table: employment
id | name                id | name                  borrower_id | company_id
1  | John Doe            1  | TechCorp              1           | 1

Table: industries        Table: company_industries  Table: loan_applications
id | name                company_id | industry_id    id  | borrower_id | property_id
1  | Technology          1          | 1              101 | 1           | 201

Table: properties
id  | address       | state
201 | 123 Main St   | TX
```

To answer "What industry does John's employer belong to?" requires 3 JOINs:
```sql
SELECT i.name FROM borrowers b
JOIN employment e ON b.id = e.borrower_id
JOIN companies c ON e.company_id = c.id
JOIN company_industries ci ON c.id = ci.company_id
JOIN industries i ON ci.industry_id = i.id
WHERE b.name = 'John Doe';
```

**Document (MongoDB) — nested documents:**
```json
{
  "_id": "APP-001",
  "borrower": {
    "name": "John Doe",
    "employment": {
      "employer": "TechCorp",
      "industry": "technology"
    }
  },
  "property": { "address": "123 Main St", "state": "TX" }
}
```

Fast for reading this one document, but answering "Find all borrowers in the same industry" requires scanning every document.

**Graph (Neo4j) — nodes and relationships:**
```
(John:Borrower) -[:WORKS_AT]→ (TechCorp:Company) -[:IN_INDUSTRY]→ (Technology:Industry)
(John) -[:APPLIED_FOR]→ (APP-001:Loan) -[:SECURED_BY]→ (123 Main St:Property) -[:LOCATED_IN]→ (Texas:State)
```

To answer the same industry question:
```cypher
MATCH (b:Borrower {name: "John Doe"})-[:WORKS_AT]->(c)-[:IN_INDUSTRY]->(i)
RETURN i.name
```

No JOINs. Just follow the arrows. And "Find all borrowers in the same industry" is equally simple:
```cypher
MATCH (b:Borrower)-[:WORKS_AT]->()-[:IN_INDUSTRY]->(i:Industry {name: "Technology"})
RETURN b.name
```

---

## 2. How Graph Databases Work Internally

This is the core concept that explains WHY graph databases are fast for relationship traversal.

### 2.1 The Key Concept: Index-Free Adjacency

In MySQL, finding related data requires scanning an index (B-tree lookup) for each JOIN. The cost of each JOIN is O(log n) where n is the table size. With 5 JOINs on tables with millions of rows, this adds up.

In Neo4j, each node stores a **direct physical pointer** (memory address) to its first relationship. Each relationship stores pointers to the next relationship for both its start and end nodes. Traversing from one node to another is just following a pointer — O(1) constant time, regardless of how many total nodes exist in the database.

**Java analogy:** MySQL is like searching a `HashMap` by key for each JOIN. Neo4j is like following `object.next` references in a `LinkedList` — direct memory access, no searching.

### 2.2 Physical Storage Structure

Neo4j stores data in fixed-size record files:

**Node Store (neostore.nodestore) — 15 bytes per record:**
```
┌─────────────────────────────────────────────────────────┐
│ Node Record (at position = nodeId × 15 bytes)           │
│                                                         │
│ byte 0:     inUse flag (is this node active?)           │
│ bytes 1-4:  first relationship ID  → pointer to rels    │
│ bytes 5-8:  first property ID      → pointer to props   │
│ bytes 9-13: labels (e.g., :Borrower)                    │
│ byte 14:    extra bits                                  │
└─────────────────────────────────────────────────────────┘

To find Node 5000: seek to position 5000 × 15 = byte 75000
INSTANT — just math, no index lookup needed.
```

**Relationship Store (neostore.relationshipstore) — 34 bytes per record:**
```
┌─────────────────────────────────────────────────────────┐
│ Relationship Record                                     │
│                                                         │
│ bytes 0-3:   start node ID        (e.g., John)          │
│ bytes 4-7:   end node ID          (e.g., TechCorp)      │
│ bytes 8-11:  relationship type    (e.g., WORKS_AT)      │
│ bytes 12-15: start node's NEXT relationship             │
│ bytes 16-19: start node's PREVIOUS relationship         │
│ bytes 20-23: end node's NEXT relationship               │
│ bytes 24-27: end node's PREVIOUS relationship           │
│ bytes 28-31: first property ID                          │
│ bytes 32-33: extra bits                                 │
└─────────────────────────────────────────────────────────┘
```

The `start_next` and `end_next` pointers form a **doubly-linked list** of relationships around each node. To find all of John's relationships, you start at his first relationship and follow the chain:

```
John's node → first_rel → WORKS_AT
  → start_next_rel → APPLIED_FOR
  → start_next_rel → NULL (end of chain)

Total: O(k) where k = number of John's relationships
NOT affected by total database size (could be 1M or 1B nodes — same speed)
```

**Property Store — linked list per node:**
```
Node: John → first_prop → {name: "John Doe"} → next → {fico: 740} → next → {income: 120000} → NULL
```

Small values (int, short string) are stored inline. Large values get a pointer to a separate dynamic store.

### 2.3 Traversal: MySQL vs Neo4j Side-by-Side

**Query: "Find the industry default rate for John's employer"**

```
MySQL approach (5 index scans):
  Step 1: Scan persons B-tree index → find id=1        O(log n)
  Step 2: Scan employment B-tree → find person_id=1    O(log n)
  Step 3: Scan companies B-tree → find id=5            O(log n)
  Step 4: Scan company_industries B-tree                O(log n)
  Step 5: Scan industries B-tree → read default_rate   O(log n)
  Total: O(5 × log n) — cost grows with table size

Neo4j approach (1 index + 4 pointer follows):
  Step 1: Index lookup: find John by name               O(log n)
  Step 2: Follow pointer → WORKS_AT relationship        O(1)
  Step 3: Follow pointer → TechCorp node                O(1)
  Step 4: Follow pointer → IN_INDUSTRY relationship     O(1)
  Step 5: Follow pointer → Technology node → read rate   O(1)
  Total: O(log n + 4) — only first step grows with size
```

With 8+ hops (e.g., fraud detection traversals), the difference becomes dramatic. MySQL: 8 × O(log n). Neo4j: O(log n) + 8 × O(1).

### 2.4 Where Properties Are Stored

Each node has its own property chain (linked list). Relationships can ALSO have properties:

```cypher
(John) -[:WORKS_AT {since: 2019, position: "Senior Engineer"}]→ (TechCorp)
```

The relationship record has its own `first_property` pointer, just like nodes. This is useful for storing metadata about the connection itself — when it started, the role, etc.

### 2.5 Indexing in Neo4j

Neo4j DOES have indexes, but they serve a different purpose than SQL:

- **SQL:** Indexes needed for EVERY query. Without index → full table scan.
- **Neo4j:** Indexes only needed for finding the STARTING node. After that, all traversal is index-free.

```cypher
-- This uses an index to find the starting node:
CREATE INDEX FOR (b:Borrower) ON (b.ssn_last4)

-- Query: index finds John, then pointer traversal for everything else
MATCH (b:Borrower {ssn_last4: "1234"})-[:WORKS_AT]->(c)-[:IN_INDUSTRY]->(i)
RETURN i.default_rate
```

You create indexes on the entry points your agents will use (borrower name, SSN, application ID). Everything after that is pointer traversal.

---

## 3. Relationship Patterns

### 3.1 One-to-Many

One company has many employees. Each WORKS_AT relationship is a separate record, forming a linked list off TechCorp's node:

```
TechCorp.first_rel → rel1(John WORKS_AT) → rel2(Jane WORKS_AT) → rel3(Bob WORKS_AT) → NULL
```

Finding all employees: follow the chain. O(number of employees). Not affected by total DB size.

### 3.2 Bidirectional

Neo4j relationships are stored ONCE with a direction but traversable in EITHER direction:

```cypher
-- Stored as: (John) -[:WORKS_AT]→ (TechCorp)
-- One relationship record with both start_node and end_node pointers

-- Forward: "Who does John work for?"
MATCH (john)-[:WORKS_AT]->(company) RETURN company

-- Backward: "Who works at TechCorp?"
MATCH (company)<-[:WORKS_AT]-(person) RETURN person

-- Either direction (no arrow):
MATCH (john)-[:WORKS_AT]-(x) RETURN x
```

### 3.3 Cyclic

Cycles are natural — just more relationship records:

```cypher
(Company A) -[:SUBSIDIARY_OF]→ (Company B) -[:SUBSIDIARY_OF]→ (Company C) -[:OWNS]→ (Company A)
```

Cypher prevents infinite loops with depth limits:
```cypher
MATCH path = (a)-[:SUBSIDIARY_OF*1..5]->(b)
-- *1..5 = follow 1 to 5 hops maximum, auto-avoids revisiting nodes
```

---

## 4. Cypher Query Language

Cypher is to Neo4j what SQL is to PostgreSQL. It uses ASCII-art patterns to describe graph traversals:

### 4.1 Basic Syntax

```cypher
-- Create a node
CREATE (b:Borrower {name: "John Doe", fico: 740, income: 120000})

-- Create a relationship
MATCH (b:Borrower {name: "John Doe"})
MATCH (c:Company {name: "TechCorp"})
CREATE (b)-[:WORKS_AT {since: 2019}]->(c)

-- MERGE = create if not exists (idempotent, like putIfAbsent)
MERGE (i:Industry {name: "Technology"})
ON CREATE SET i.default_rate = 0.032

-- Query: pattern matching
MATCH (b:Borrower)-[:WORKS_AT]->(c:Company)-[:IN_INDUSTRY]->(i:Industry)
WHERE b.fico > 700
RETURN b.name, c.name, i.name, i.default_rate
```

### 4.2 Underwriting-Specific Queries

```cypher
-- Industry risk profiling (3-hop traversal)
MATCH (b:Borrower {ssn_last4: "1234"})
      -[:WORKS_AT]->(c:Company)
      -[:IN_INDUSTRY]->(i:Industry)
RETURN i.name, i.default_rate

-- Similar past loans in same industry with outcomes
MATCH (b:Borrower)-[:WORKS_AT]->(:Company)-[:IN_INDUSTRY]->(i:Industry {name: "cryptocurrency"})
MATCH (b)-[:APPLIED_FOR]->(la:LoanApplication)
WHERE la.status IN ["approved", "defaulted"]
RETURN la.status, COUNT(*) as count, AVG(b.fico) as avg_fico

-- Regulatory mapping: property → state → all applicable regulations
MATCH (p:Property {address: "123 Main St"})
      -[:LOCATED_IN]->(s:State)
      -[:GOVERNED_BY]->(r:Regulation)
RETURN r.name, r.max_ltv, r.description

-- Fraud network detection (variable depth)
MATCH path = (b:Borrower {name: "John"})-[*1..6]-(flagged {fraud_flag: true})
RETURN path
```

### 4.3 Why LLMs Generate Cypher Better Than Complex SQL

Cypher's ASCII-art pattern matching is closer to natural language than SQL JOINs. When an AI agent needs to dynamically generate a query, Cypher is more reliable:

```
Natural language: "Find all borrowers in the same industry whose loans defaulted"

LLM-generated Cypher (usually correct):
  MATCH (b:Borrower)-[:WORKS_AT]->(c:Company)-[:IN_INDUSTRY]->(i:Industry)
  MATCH (b)-[:APPLIED_FOR]->(la:LoanApplication {status: "defaulted"})
  RETURN b.name, i.name, la.amount

LLM-generated SQL (often wrong for 5+ JOINs):
  SELECT b.name, i.name, la.amount
  FROM borrowers b
  JOIN employment e ON b.id = e.borrower_id
  JOIN companies c ON e.company_id = c.id
  JOIN company_industries ci ON c.id = ci.company_id
  JOIN industries i ON ci.industry_id = i.id
  JOIN loan_applications la ON b.id = la.borrower_id
  WHERE la.status = 'defaulted'
  -- LLMs often miss JOIN conditions or get table aliases wrong
```

LangChain provides `GraphCypherQAChain` for this — the agent asks in English, the LLM writes Cypher, Neo4j executes it.

---

## 5. Neo4j Setup: Docker + Python

### 5.1 Docker Setup (Development)

```bash
docker run -d \
  --name neo4j-underwriting \
  -p 7474:7474 \
  -p 7687:7687 \
  -e NEO4J_AUTH=neo4j/password123 \
  neo4j:community
```

Browser UI: http://localhost:7474 — Port 7474 = HTTP browser, 7687 = Bolt protocol for Python driver.

### 5.2 Python Driver

```python
from neo4j import GraphDatabase

driver = GraphDatabase.driver(
    "bolt://localhost:7687",
    auth=("neo4j", "password123")
)

def run_query(query: str, params: dict = None) -> list:
    with driver.session() as session:
        result = session.run(query, params or {})
        return [record.data() for record in result]
```

### 5.3 LangChain Integration

```python
from langchain_community.graphs import Neo4jGraph

graph = Neo4jGraph(
    url="bolt://localhost:7687",
    username="neo4j",
    password="password123"
)

# Auto-discovers schema for LLM context
print(graph.schema)
```

---

## 6. Underwriting Knowledge Graph Design

### 6.1 Entity Model

```
NODE TYPES:
  :Borrower     {name, fico, ssn_last4, annual_income}
  :Company      {name, founded, employee_count}
  :Industry     {name, default_rate, avg_recovery}
  :Property     {address, value, sqft}
  :State        {name, code}
  :Regulation   {name, jurisdiction, max_ltv, description}
  :LoanApplication {id, amount, status, type}

RELATIONSHIP TYPES:
  WORKS_AT      Borrower → Company        {since, position}
  IN_INDUSTRY   Company → Industry
  APPLIED_FOR   Borrower → LoanApplication
  SECURED_BY    LoanApplication → Property
  LOCATED_IN    Property → State
  GOVERNED_BY   State → Regulation
  HAS_RISK      Industry → RiskProfile
```

### 6.2 Seed Data Pattern

```python
def seed_underwriting_graph(graph):
    graph.query("""
        MERGE (tech:Industry {name: "technology"})
        SET tech.default_rate = 0.032, tech.avg_recovery = 0.72
        MERGE (crypto:Industry {name: "cryptocurrency"})
        SET crypto.default_rate = 0.08, crypto.avg_recovery = 0.45
        MERGE (healthcare:Industry {name: "healthcare"})
        SET healthcare.default_rate = 0.018, healthcare.avg_recovery = 0.85

        MERGE (techcorp:Company {name: "TechCorp Inc"})
        SET techcorp.founded = 2015, techcorp.employee_count = 500
        MERGE (techcorp)-[:IN_INDUSTRY]->(tech)

        MERGE (john:Borrower {ssn_last4: "1234"})
        SET john.name = "John Doe", john.fico = 740, john.annual_income = 120000
        MERGE (john)-[:WORKS_AT {since: 2019}]->(techcorp)

        MERGE (app:LoanApplication {id: "APP-001"})
        SET app.amount = 350000, app.status = "pending"
        MERGE (john)-[:APPLIED_FOR]->(app)

        MERGE (prop:Property {address: "123 Main St"})
        SET prop.value = 440000
        MERGE (app)-[:SECURED_BY]->(prop)

        MERGE (tx:State {name: "Texas", code: "TX"})
        MERGE (prop)-[:LOCATED_IN]->(tx)

        MERGE (sec50:Regulation {name: "Section 50(a)(6)"})
        SET sec50.max_ltv = 0.80
        MERGE (tx)-[:GOVERNED_BY]->(sec50)
    """)
```

### 6.3 Graph Tools for Agents

```python
@tool
def get_borrower_risk_context(ssn_last4: str) -> dict:
    """Get risk context by traversing borrower → employer → industry."""
    result = graph.query("""
        MATCH (b:Borrower {ssn_last4: $ssn})-[:WORKS_AT]->(c:Company)-[:IN_INDUSTRY]->(i:Industry)
        OPTIONAL MATCH (b2:Borrower)-[:WORKS_AT]->(:Company)-[:IN_INDUSTRY]->(i)
        OPTIONAL MATCH (b2)-[:APPLIED_FOR]->(la:LoanApplication)
        RETURN b.name, c.name as employer, i.name as industry, i.default_rate,
               COUNT(la) as similar_loans,
               SUM(CASE WHEN la.status = 'defaulted' THEN 1 ELSE 0 END) as defaults
    """, {"ssn": ssn_last4})
    return result[0] if result else {"error": "Borrower not found"}

@tool
def find_similar_past_loans(industry: str) -> list:
    """Find past loans from borrowers in the same industry."""
    return graph.query("""
        MATCH (b:Borrower)-[:WORKS_AT]->(:Company)-[:IN_INDUSTRY]->(i:Industry {name: $industry})
        MATCH (b)-[:APPLIED_FOR]->(la:LoanApplication)
        RETURN b.name, b.fico, la.amount, la.status ORDER BY la.status
    """, {"industry": industry})

@tool
def get_state_regulations(state_code: str) -> list:
    """Get all regulations for a specific state."""
    return graph.query("""
        MATCH (s:State {code: $code})-[:GOVERNED_BY]->(r:Regulation)
        RETURN r.name, r.max_ltv, r.description
    """, {"code": state_code})
```

---

## 7. Why Knowledge Graphs Matter for AI Agents

### 7.1 RAG vs. Knowledge Graph — Complementary, Not Competing

| Dimension | RAG (Vector DB) | Knowledge Graph |
|-----------|-----------------|-----------------|
| Finds | What documents SAY | What data SHOWS |
| Example | "Policy says crypto is high-risk" | "25% of similar loans defaulted" |
| Data type | Unstructured text | Structured entities + relationships |
| Search method | Semantic similarity | Relationship traversal |
| Best for | Policy lookup, compliance text | Risk profiling, similar loans, fraud |

**Neither alone gives the full picture.** Combined: policy knowledge + data-driven risk assessment.

### 7.2 Why AI Agents Made Graph DB More Important

Before AI agents: developers write fixed SQL for specific screens. With AI agents: the LLM decides AT RUNTIME which relationships to follow. This dynamic, unpredictable, multi-hop traversal is exactly what graph databases excel at.

### 7.3 Concrete Underwriting Example

**Without graph:** Agent gets generic policy text: "Crypto is flagged as high-risk per policy."  
**With graph + RAG:** Agent gets specific data: "25% of similar loans defaulted, avg defaulter FICO 695, this borrower's FICO 710 is only 15 points above." → MANUAL_REVIEW with specific, data-driven reasoning.

---

## 8. Popular Graph Databases

| Database | Query Language | Best For | Why/Why Not for Us |
|----------|---------------|----------|-------------------|
| Neo4j | Cypher (most intuitive) | General purpose, best tooling | ✅ Best LangChain integration, free Docker |
| Amazon Neptune | Gremlin / SPARQL | AWS-managed | ❌ Less intuitive, $73/mo minimum |
| TigerGraph | GSQL | Large-scale analytics | ❌ Enterprise-only |
| ArangoDB | AQL | Multi-model (doc + graph) | ⚠️ Interesting but less community |

---

## 9. Architecture: Polyglot Persistence

Don't replace MongoDB. Add Neo4j alongside as a secondary, read-only store for AI agents only. Sync ~10% of data (entities + relationships).

| Store | Purpose | Used By |
|-------|---------|---------|
| MongoDB (DocumentDB) | Primary CRUD, UI, reports | Kuber app |
| Neo4j | Relationship traversal, risk context | AI agents only |
| FAISS / OpenSearch | Semantic search, RAG | AI agents only |
| Redis | Caching | Both |
| PostgreSQL | Analytics (via Glue ETL) | Reporting |

You already do this pattern (DocumentDB → Redis → PostgreSQL). Adding Neo4j follows the same principle.

---

## 10. Q&A

### Q: What does graph DB do that MySQL can't?
Same results possible with JOINs. Difference: 1-2 JOINs → MySQL fine. 5+ JOINs → MySQL painful (index scans multiply). Graph stays fast (pointer follows are O(1) per hop regardless of DB size).

### Q: Why have I never used graph DB?
Most apps need 1-2 level relationships. Kuber CRUD (loan → borrowers → payments) is perfect for MongoDB. Graph only shines at 5+ hop traversals.

### Q: Why famous now?
AI agents ask unpredictable multi-hop questions at runtime. RAG misses relationship context. LLMs generate Cypher better than complex SQL.

### Q: Replace MongoDB with graph for Kuber?
No. MongoDB is perfect for CRUD/UI. Add Neo4j alongside for AI agents only. Polyglot persistence.

### Q: Neo4j vs Neptune?
Neo4j: best Cypher, free Docker, best LangChain. Neptune: AWS managed, Gremlin (less intuitive), $73/mo min. Neo4j for learning, either for production.

### Q: Does data replication make sense?
Yes. Same pattern as DocumentDB → Redis → PostgreSQL. Different stores for different access patterns.

---

## 11. Assignments (Completed ✅)

- [x] Neo4j Docker running + Python connected
- [x] UnderwritingGraph class with CRUD + queries
- [x] Seed data (borrowers, industries, regulations)
- [x] Graph tools as @tool for agents
- [x] Cypher traversal queries tested
- [x] Tests + docs updated
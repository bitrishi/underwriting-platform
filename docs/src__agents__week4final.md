from docx import Document
from docx.shared import Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH

doc = Document()
s = doc.styles['Normal']; s.font.name = 'Calibri'; s.font.size = Pt(11)
s.paragraph_format.space_after = Pt(6)

def h0(t):
    h = doc.add_heading(t, 0); h.alignment = WD_ALIGN_PARAGRAPH.CENTER
def h1(t): doc.add_heading(t, 1)
def h2(t): doc.add_heading(t, 2)
def p(t): doc.add_paragraph(t)
def bp(l, t):
    pr = doc.add_paragraph(); r = pr.add_run(l); r.bold = True; pr.add_run(t)
def tbl(headers, rows):
    t = doc.add_table(rows=1+len(rows), cols=len(headers))
    t.style = 'Light Grid Accent 1'
    for i, h in enumerate(headers):
        c = t.rows[0].cells[i]; c.text = h
        for pr in c.paragraphs:
            for r in pr.runs: r.bold = True; r.font.size = Pt(10)
    for ri, row in enumerate(rows, 1):
        for ci, v in enumerate(row):
            c = t.rows[ri].cells[ci]; c.text = v
            for pr in c.paragraphs:
                for r in pr.runs: r.font.size = Pt(10)
    doc.add_paragraph()

h0('Week 4: Complete Reference\nLangGraph & Multi-Agent Orchestration')

bp('Focus: ', 'Converting sequential pipeline into production-grade orchestrated graph with parallel execution, conditional routing, error handling, human-in-the-loop, checkpointing, and streaming.')

# DAY 1
h1('Day 1: LangGraph Fundamentals')

h2('Five Problems with Sequential Code')
bp('No Parallel Execution: ', 'Independent agents run one after another. FetchData (3s) + DocReview (5s) = 8s sequential vs 5s parallel. 37% improvement at 1,000 loans/day saves hours.')
bp('No Conditional Routing: ', 'No documents? Sequential either wastes money calling DocReview or requires unmaintainable if/else trees.')
bp('No Error Recovery: ', 'Risk Scoring fails? Restart from scratch. Even 1% failure rate = 10 full restarts daily at 1,000 evaluations.')
bp('No Human-in-the-Loop: ', 'MANUAL_REVIEW requires human input hours later. Sequential Python cannot pause and resume.')
bp('No Visibility: ', 'Only final result visible. No execution history showing which steps ran.')

h2('What LangGraph Is')
p('Framework for stateful multi-step AI applications as directed graphs. Nodes are functions reading/writing shared state. Edges define execution flow. Built on LangChain for AI agent orchestration.')
p('Step Functions analogy: Task state = node function. Choice state = conditional edge. Parallel state = fan-out. Wait callback = interrupt(). For production, use both: Step Functions for infrastructure, LangGraph for agent orchestration.')

h2('Core Concepts')
bp('State (TypedDict): ', 'Shared data across all nodes. Each node reads what it needs, returns partial update. Annotated reducers merge parallel writes. Like a shared DTO through a pipeline.')
bp('Nodes: ', 'Functions taking state, returning updates. Your existing agents become implementations INSIDE nodes. Thin wrapper: read state, call agent, write results.')
bp('Edges: ', 'Normal (unconditional), conditional (Python function returns next node), and START/END points. All routing deterministic — no LLM calls for routing.')
bp('Compilation: ', 'Validates graph structure at compile time. All referenced nodes exist, paths to END exist, no unreachable nodes.')

# DAY 1 Q&A
h2('Day 1 Q&A: State Persistence')

bp('Checkpoint stores: ', 'Redis (BEST fit — key-value, fast, TTL, you already have it). PostgreSQL (convenience, queryable but overkill). DynamoDB (AWS-managed). MemorySaver (dev only).')
bp('Inter-node communication: ', 'IN-MEMORY state within single process. Checkpoint store is BACKUP, not communication path. No database round-trip between nodes.')
bp('Context compression: ', 'NOT needed for pipeline (5-10K tokens, 200K limit). Matters for long chat sessions. Strategies: summarization, trimming, fact extraction.')
bp('Parallel safety: ', 'No ConcurrentModificationException. Nodes get read-only snapshots, return independent updates. LangGraph merges AFTER all complete in single thread. Like CompletableFuture.allOf().')
bp('Reducers: ', 'For same-field parallel writes. add reducer concatenates lists. Runs during single-threaded merge. Not a lock — a merge strategy.')

# DAY 2
h1('Day 2: Parallel Execution, Error Handling & Compliance')

h2('Parallel Execution')
p('Graph topology defines concurrency. Two edges from same source = parallel. Multiple incoming edges = wait for all (join). Uses asyncio — I/O-bound agents work perfectly with GIL.')
p('Empty documents: always start doc_review, let node handle empty case internally. Returns SKIPPED instantly. Business logic in node, not topology.')

h2('Error Handling')
bp('Per-node try/except: ', 'On failure: output = None, append error, continue. Like @CircuitBreaker.')
bp('Fatal error routing: ', 'FetchData cannot identify borrower? Conditional edge skips to final_decision with error report.')
bp('Safe default: ', 'Uncertainty = escalate to human. Compliance failure = human MUST review.')

h2('Compliance Agent')
bp('What it checks: ', 'Fair lending (ECOA — denial reasons based on financial factors only). Disclosures (TRID timing). State procedures. Audit trail completeness.')
bp('Override power: ', 'Can change APPROVE to MANUAL_REVIEW on regulatory violation. Compliance takes precedence.')
bp('Model: ', 'Sonnet for legal reasoning. 12x Haiku cost justified by legal consequences.')
bp('Tools: ', 'Two RAG (existing) + two deterministic (TRID rules and audit check in Python — hard rules should never be LLM judgment).')

h2('Day 2 Q&A: One vs Many Agents')
bp('Decision checklist: ', '(1) More than 10 tools? (2) Different models needed? (3) Independent parallel tasks? (4) Isolated error handling? (5) Contradictory prompts? (6) Independent deployment? Any "yes" = consider splitting.')
bp('Grouping principle: ', 'By capability domain AND model requirement. Not per-tool (over-engineering) and not everything in one (accuracy loss).')

# DAY 3
h1('Day 3: CrewAI Comparison')

h2('Philosophy')
p('LangGraph: graphs (explicit control). CrewAI: teams (role-based, framework infers flow). Like Step Functions vs Spring Batch.')

h2('Real Differences')
bp('State: ', 'LangGraph passes TYPED STATE (integer 740). CrewAI passes NATURAL LANGUAGE ("FICO 740" as string). For financial precision, typed state essential.')
bp('Parallel: ', 'LangGraph native. CrewAI sequential/hierarchical only.')
bp('Conditional routing: ', 'LangGraph has edge functions. CrewAI has none.')
bp('Checkpointing: ', 'LangGraph built-in. CrewAI none — restart from scratch.')
bp('Human-in-loop: ', 'LangGraph interrupt() persists across sessions. CrewAI blocks synchronously.')

h2('Decision')
p('LangGraph for production (the company underwriting). CrewAI for prototypes and demos. Same tools and LLMs — only orchestration differs. Migration requires rethinking data flow (string to typed).')

# DAY 4
h1('Day 4: Human-in-the-Loop & Checkpointing')

h2('The Lifecycle')
p('Graph runs 4 agents. Compliance sets needs_manual_review=True. Conditional edge routes to human_review. Node calls interrupt() with review summary. ENTIRE state saved to Redis. Graph RETURNS (not blocks). Process can exit. Nothing runs.')
p('Hours later: human responds. API resumes with same thread_id. LangGraph loads checkpoint, reconstructs state, injects response. Continues from human_review. Final decision produced.')

h2('Key Insights')
bp('Nothing runs during pause: ', 'Not a sleeping thread. State machine stops. State in Redis. New process resumes later. Like SF callback tasks.')
bp('Full snapshots: ', 'Each checkpoint contains ENTIRE state. Self-contained resume from any point. No delta replay needed.')
bp('thread_id: ', 'String you choose (use app_id). LangGraph matches it to checkpoint on resume. Does not understand human response semantics — handles pause/persist/resume mechanics.')
bp('Storage: ', '~10 KB per checkpoint, ~350 MB max with 7-day TTL. Redis handles trivially.')

h2('Production API')
p('Three endpoints: Start Evaluation (returns result or pending_review). Get Pending Reviews (UI queries interrupted executions). Submit Decision (resumes graph). Cleanly separates automated execution from human workflow.')

# DAY 5
h1('Day 5: Advanced Patterns')

h2('Subgraphs')
p('Graphs nested inside nodes. Use when node has internal conditional logic, for reusability across pipelines, or for team ownership boundaries. Do NOT use for simple nodes. Start flat, extract when complexity demands it.')

h2('Streaming')
bp('Layer 1: ', 'Token streaming from LLM API (words appearing). Every LLM supports this.')
bp('Layer 2: ', 'Tool call streaming (ReAct loop). What verbose=True shows.')
bp('Layer 3: ', 'Node completion streaming (LangGraph-specific). Pipeline progress. Like Claude Code showing "Searching... Writing..."')

h2('Dynamic Routing')
p('Build graph from input data (loan type). Like Spring profiles. LLM routing only for decisions genuinely requiring judgment — use sparingly.')

h2('Cycles')
p('Human requests more data — loop back to fetch, re-score, return to human. Always set max_iterations (3-5). Cycles are exception paths, not primary flow.')

h2('Versioning')
p('Version in thread_id. Keep old graph definitions until checkpoints expire via TTL. No migration needed.')

h2('Deployment')
p('One ECS Fargate service, NOT Lambda per node. Cold starts (2-15s), state transfer overhead, dependency duplication make Lambda-per-node impractical. Same pattern as Kuber services.')

# WEEKEND
h1('Weekend BUILD: Complete Orchestrator')

h2('Architecture')
p('6 nodes: fetch_data + doc_review (parallel) → risk_scoring → compliance → [human_review OR final_decision] → END. Error path: fatal fetch failure skips to final_decision.')

h2('Production Metrics')
tbl(
    ['Metric', 'Value'],
    [
        ['Sub-agents', '4 (FetchData, DocReview, RiskScoring, Compliance)'],
        ['Tools', '20+'],
        ['Data sources', '3 (calculations, RAG, knowledge graph)'],
        ['Models', 'Haiku + Sonnet'],
        ['Cost/eval', '$0.025-0.035'],
        ['Time/eval', '~11 seconds automated'],
        ['Checkpoints', '~350 MB max (Redis, 7-day TTL)'],
    ]
)

h2('Error Philosophy')
p('Produce best assessment with available data. Document gaps explicitly. Partial results better than no results. Only complete FetchData failure is fatal. Everything else degrades gracefully.')

h2('What Makes It Production-Grade')
bp('Typed state: ', 'DTI is a float, not "about 40%"')
bp('Deterministic where possible: ', 'Calculations and routing in Python. LLM for reasoning only.')
bp('Isolated failures: ', 'Each node independent.')
bp('Auditability: ', 'Structured data for regulatory examination.')
bp('Human oversight: ', 'MANUAL_REVIEW escalation for uncertain cases.')
bp('Cost predictability: ', 'Bounded per evaluation. No infinite loops.')
bp('Resumability: ', 'Checkpointing. No work lost on failure.')

# SUMMARY TABLE
h1('Week 4 Complete Summary')
tbl(
    ['Concept', 'What It Does', 'Java / AWS Equivalent'],
    [
        ['StateGraph', 'Defines orchestration', 'SF definition'],
        ['Node', 'Processing step', 'Task / Lambda'],
        ['Conditional edge', 'Routes on state', 'Choice state'],
        ['Parallel', 'Concurrent independent nodes', 'Parallel state'],
        ['TypedDict state', 'Shared data', 'Shared DTO'],
        ['Reducer', 'Merges parallel writes', 'ConcurrentLinkedQueue'],
        ['Checkpointing', 'Crash recovery', 'SF execution history'],
        ['interrupt()', 'Human-in-the-loop', 'SF callback'],
        ['thread_id', 'Execution identity', 'SF execution ARN'],
        ['Streaming', 'Progress updates', 'SF events'],
        ['Subgraph', 'Nested graph', 'Microservice internals'],
        ['Cycles', 'Iterative loops', 'Retry loops'],
        ['CrewAI', 'Team-based alternative', 'Spring Batch'],
        ['Fargate service', 'Full pipeline in-process', 'Kuber pattern'],
        ['Compliance override', 'Legal veto', 'Regulatory authority'],
    ]
)

pr = doc.add_paragraph()
r = pr.add_run('AI Underwriting Agent Learning Journey | Week 4 Complete Reference')
r.font.size = Pt(9); r.font.color.rgb = RGBColor(128, 128, 128)
pr.alignment = WD_ALIGN_PARAGRAPH.CENTER
doc.save('Week4_Complete_Reference.docx')
print('✅ DOCX created')
# Week 1 — Day 1: Python for Java Developers

**Date:** Session 1  
**Duration:** 30 minutes theory + assignment  
**Status:** ✅ Complete

---

## Topics Covered

1. Variables & Types
2. Collections (list, dict, tuple, set)
3. Functions & Type Hints
4. Classes & Dataclasses
5. Control Flow
6. Decorators
7. Memory Management (Reference Counting, GIL)
8. Functional Interfaces (Not Needed in Python)
9. Encapsulation (Convention vs. Enforcement)
10. Lambdas & List Comprehensions
11. Compiler (There Isn't One)
12. Concurrency (async/await, threading, multiprocessing)

---

## 1. Variables and Types

Python infers types at runtime. No declarations needed.

**Java:**

```java
String name = "Rishi";
int age = 30;
double salary = 150000.50;
boolean isActive = true;
List<String> skills = new ArrayList<>();
```

**Python:**

```python
name = "Rishi"              # str (inferred)
age = 30                     # int (inferred)
salary = 150000.50           # float (inferred)
is_active = True             # bool (capital T/F!)
skills = []                  # list (no generics needed)
```

**Key differences:**

- No semicolons. Ever.
- `snake_case` everywhere (not `camelCase`)
- `True` / `False` / `None` are capitalized (Java: `true` / `false` / `null`)
- Everything is an object. No primitives. No autoboxing.

---

## 2. Collections: The Big Four

### List (Java's ArrayList)

```python
names = ["a", "b", "c"]
names.append("d")            # Java: names.add("d")
names[0]                      # Java: names.get(0)
len(names)                    # Java: names.size()
```

### Dict (Java's HashMap)

```python
scores = {"fico": 740, "dti": 24}
scores["fico"]                # Java: scores.get("fico")
scores["ltv"] = 80            # Java: scores.put("ltv", 80)
```

### Tuple (immutable — no Java equivalent)

```python
point = (10, 20)
x, y = point                 # "unpacking" — assigns 10 to x, 20 to y
```

### Set (Java's HashSet)

```python
tags = {"loan", "active"}
tags.add("approved")
```

**Mental model:** `[]` = list, `{}` = dict, `()` = tuple. All built-in literals. No `new`, no imports.

---

## 3. Functions and Type Hints

**Java:**

```java
public double calculateDti(double income, double monthlyDebt) {
    return (monthlyDebt * 12) / income;
}
```

**Python (without type hints):**

```python
def calculate_dti(income, monthly_debt):
    return (monthly_debt * 12) / income
```

**Python (with type hints — recommended for agents):**

```python
def calculate_dti(income: float, monthly_debt: float) -> float:
    return (monthly_debt * 12) / income
```

**Why type hints matter for agents:** LangChain's `@tool` decorator reads type hints to auto-generate the tool schema. The LLM uses that schema to know what arguments to pass. Bad type hints = broken tool calls.

**Default arguments (replaces Java method overloading):**

```python
def score_risk(fico: int, dti: float, ltv: float = 80.0) -> str:
    if fico > 700 and dti < 30:
        return "LOW_RISK"
    return "HIGH_RISK"

# Can call as:
score_risk(740, 24)           # ltv defaults to 80.0
score_risk(740, 24, 95.0)    # ltv explicitly set
```

---

## 4. Classes and Dataclasses

**Java:**

```java
public class LoanApplication {
    private String borrowerName;
    private double loanAmount;
    private int ficoScore;

    public LoanApplication(String borrowerName, double loanAmount, int ficoScore) {
        this.borrowerName = borrowerName;
        this.loanAmount = loanAmount;
        this.ficoScore = ficoScore;
    }

    public boolean isEligible() {
        return this.ficoScore >= 680 && this.loanAmount <= 500000;
    }

    @Override
    public String toString() {
        return "LoanApplication{" + borrowerName + ", " + loanAmount + "}";
    }
}
```

**Python:**

```python
class LoanApplication:
    def __init__(self, borrower_name: str, loan_amount: float, fico_score: int):
        self.borrower_name = borrower_name
        self.loan_amount = loan_amount
        self.fico_score = fico_score

    def is_eligible(self) -> bool:
        return self.fico_score >= 680 and self.loan_amount <= 500000

    def __str__(self) -> str:
        return f"LoanApplication({self.borrower_name}, {self.loan_amount})"
```

**Key mappings:**

| Java | Python |
|------|--------|
| `constructor` | `__init__(self, ...)` |
| `this` | `self` (must be first parameter) |
| `toString()` | `__str__()` |
| `&&` | `and` |
| `\|\|` | `or` |
| `!` | `not` |

**Dataclasses (Python's Lombok @Data):**

```python
from dataclasses import dataclass

@dataclass
class LoanDecision:
    decision: str
    confidence: float
    reasons: list[str]
```

Auto-generates `__init__`, `__str__`, `__eq__`. Pydantic `BaseModel` is the supercharged version — Lombok + Jackson + Bean Validation combined.

---

## 5. Control Flow

**Java:**

```java
if (fico >= 740) {
    risk = "LOW";
} else if (fico >= 680) {
    risk = "MEDIUM";
} else {
    risk = "HIGH";
}

for (String name : names) { ... }

for (int i = 0; i < 10; i++) { ... }

try { ... }
catch (Exception e) { ... }
finally { ... }
```

**Python:**

```python
if fico >= 740:
    risk = "LOW"
elif fico >= 680:
    risk = "MEDIUM"
else:
    risk = "HIGH"

for name in names:
    ...

for i in range(10):
    ...

try:
    ...
except Exception as e:
    ...
finally:
    ...
```

**Remember:** `elif` (not `else if`), `except` (not `catch`), colon `:` + indentation (not braces).

---

## 6. Decorators

Decorators wrap a function with extra behavior — like Spring's `@Transactional`.

**Java (Spring AOP):**

```java
@Transactional
public void processLoan() {
    // Spring wraps with begin/commit/rollback
}
```

**Python:**

```python
@tool
def pull_credit(ssn: str) -> dict:
    """Pull credit score for a borrower."""
    return credit_api.pull(ssn)
```

**What `@tool` does internally:**

1. Reads function name → `"pull_credit"`
2. Reads docstring → `"Pull credit score for a borrower."`
3. Reads type hints → `input: {ssn: string}, output: dict`
4. Creates a Tool object with name, description, schema, function reference
5. The LLM receives this schema and uses it to decide when to call the tool

**That's why docstrings and type hints are critical — they ARE the tool's API contract.**

---

## 7. Memory Management

**Java:**

- Stack (local vars, references) + Heap (objects via `new`)
- Garbage collector runs periodically → can cause pauses
- Tuning: `-Xmx`, `-Xms`, G1GC / ZGC flags
- Multi-threaded: each thread gets its own stack

**Python:**

- Everything on the heap. Variables are just name → object pointers
- **Reference counting:** freed IMMEDIATELY when refcount hits 0
- Generational GC only for circular references (rare)
- **GIL:** only one thread executes Python bytecode at a time
- Uses `async/await` for concurrency (not threads)

**For agents:** Memory is rarely a concern. Each invocation is short-lived. Your bottleneck is LLM API latency (2-5 seconds), not CPU or memory.

---

## 8. Functional Interfaces: Not Needed

**Java** needs `@FunctionalInterface`, `Function<T,R>`, `Predicate<T>` to pass behavior around.

**Python:** Functions ARE objects. Pass them directly.

```python
def evaluate_risk(fico, dti):
    if fico > 700:
        return "LOW"
    return "HIGH"

# Assign function to variable
my_eval = evaluate_risk

# Pass function to agent framework
tools = [pull_credit, calculate_dti]
agent = create_agent(tools=tools)
```

No interfaces, no wrapping. This is why Python is natural for agent development.

---

## 9. Encapsulation: Convention Over Enforcement

**Java:** Compiler-enforced. `private` means private. Period.

**Python:** Convention-based. "We're all consenting adults."

```python
class BorrowerProfile:
    def __init__(self, name, ssn, income):
        self.name = name           # public (no prefix)
        self._income = income      # "protected" — convention only
        self.__ssn = ssn           # "private" — name-mangled
```

- No prefix = public
- `_name` = "don't touch from outside" (not enforced)
- `__name` = name-mangled to `_ClassName__name` (awkward but not impossible)
- `@property` decorators add getter/setter logic with validation

---

## 10. Lambdas and List Comprehensions

**Java (Streams):**

```java
applications.stream()
    .filter(app -> app.getFico() >= 680)
    .map(app -> app.getBorrowerName())
    .collect(Collectors.toList());
```

**Python (List Comprehensions):**

```python
eligible_names = [
    app.borrower_name
    for app in applications
    if app.fico >= 680
]
```

**Python lambdas are single-expression only:**

```python
check = lambda fico: fico >= 680

# For anything complex, use a named function instead
sorted_apps = sorted(applications, key=lambda app: app.fico, reverse=True)
```

---

## 11. Compiler: There Isn't One

**Java:** `javac` → `.class` bytecode → JVM. Errors caught before runtime.

**Python:** Interpreted line-by-line. Errors discovered at runtime only.

**Safety nets replacing the compiler:**

| Java Safety | Python Equivalent |
|-------------|-------------------|
| Compiler type checking | `mypy` (optional static type checker) |
| IDE red squiggles | PyCharm / VS Code Pylance |
| Unit tests | `pytest` (Python's JUnit) |
| Build-time checks | `ruff` / `flake8` (linters) |
| Runtime validation | **Pydantic** (essential for agents) |

---

## 12. Concurrency: Four Models

### The Key Insight

Agent development is **I/O-bound** (waiting for API responses), not CPU-bound. The GIL is irrelevant for I/O.

| Operation | Time | Bottleneck |
|-----------|------|------------|
| Bedrock LLM call | 2,000–5,000ms | Network I/O |
| Credit bureau API | 300–800ms | Network I/O |
| OpenSearch query | 100–300ms | Network I/O |
| Python logic | 1–5ms | CPU (negligible) |

### Model 1: async/await (Primary tool for agents)

Single thread, switches tasks during I/O waits.

```python
import asyncio

async def fetch_borrower(app_id: str) -> dict:
    result = await bedrock_client.invoke(prompt)    # pauses here
    return result                                     # other tasks ran during wait

async def evaluate_loan(app_id: str, ssn: str):
    # Run both concurrently — total time = max(both), not sum
    borrower, credit = await asyncio.gather(
        fetch_borrower(app_id),
        pull_credit(ssn)
    )
    return assess(borrower, credit)
```

**Java equivalent:** `CompletableFuture.allOf(a, b).join()`

### Model 2: Threading (For legacy sync libraries)

GIL is released during I/O. Works fine for I/O-bound work.

```python
from concurrent.futures import ThreadPoolExecutor

with ThreadPoolExecutor(max_workers=5) as pool:
    future_credit = pool.submit(credit_api.pull, ssn)
    future_employ = pool.submit(employ_api.verify, ssn)
    credit = future_credit.result()
    employ = future_employ.result()
```

### Model 3: Multiprocessing (For CPU-bound batch work)

Separate processes with separate GILs. True parallel execution.

```python
from multiprocessing import Pool

with Pool(processes=4) as pool:
    results = pool.map(score_application, all_applications)
```

### Model 4: C Extensions (NumPy, Pandas, PyTorch)

Written in C/C++. GIL released during native code. This is why Python powers AI/ML.

### Summary Table

| Model | GIL Impact | Use Case | Java Equivalent |
|-------|-----------|----------|-----------------|
| async/await | None (I/O) | Agent orchestration | CompletableFuture |
| Threading | None for I/O | Legacy sync libs | ExecutorService |
| Multiprocessing | Bypassed | Batch ML scoring | ProcessBuilder |
| C Extensions | Released | NumPy, ML inference | JNI / native libs |

---

## Cheat Sheet: Java → Python

| Java | Python |
|------|--------|
| `String name = "x";` | `name = "x"` |
| `camelCase` | `snake_case` |
| `true` / `false` / `null` | `True` / `False` / `None` |
| `{ }` braces | `:` + indentation |
| `this.field` | `self.field` |
| `&&` `\|\|` `!` | `and` `or` `not` |
| `try / catch / finally` | `try / except / finally` |
| `@Data` (Lombok) | `@dataclass` |
| `@Transactional` | `@decorator` |
| `toString()` | `__str__()` |
| `constructor` | `__init__(self, ...)` |
| `List.of()` / `Map.of()` | `[]` / `{}` |
| `System.out.println(x)` | `print(x)` |
| `pom.xml` | `requirements.txt` |
| `private` / `public` | `_prefix` / no prefix |
| `Function<T,R>` | Functions are objects |
| `.stream().filter().map()` | `[x for x in list if cond]` |
| `javac → bytecode → JVM` | Interpreted → use mypy + Pydantic |
| `-Xmx` / G1GC tuning | Reference counting (automatic) |
| `CompletableFuture` | `async/await` + `asyncio.gather()` |

---

## Assignment (Completed ✅)

- [x] Task 1: `LoanApplication` class with type hints
- [x] Task 2: `LoanDecision` dataclass
- [x] Task 3: `evaluate_applications()` with list comprehension
- [x] Task 4: `@log_call` decorator
- [x] Task 5: Async concurrent simulation
- [x] Task 6: This markdown file
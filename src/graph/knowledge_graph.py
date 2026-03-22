"""Neo4j-backed knowledge graph for underwriting context traversal."""

from __future__ import annotations

from neo4j import GraphDatabase


class UnderwritingGraph:
    """Graph client for borrower, company, industry, property, and regulation data."""

    def __init__(self, uri: str, user: str, password: str):
        self.driver = GraphDatabase.driver(uri, auth=(user, password))

    def close(self) -> None:
        """Close underlying Neo4j driver."""
        self.driver.close()

    def verify_connection(self) -> bool:
        """Return True when a basic query executes successfully."""
        with self.driver.session() as session:
            value = session.run("RETURN 1 AS ok").single()["ok"]
            return value == 1

    def clear_graph(self) -> None:
        """Delete all nodes and relationships. Intended for local dev/tests only."""
        with self.driver.session() as session:
            session.run("MATCH (n) DETACH DELETE n")

    # ----------------------------
    # Node creation methods
    # ----------------------------
    def add_borrower(
        self,
        *,
        name: str,
        fico: int,
        ssn_last4: str,
        annual_income: float,
    ) -> None:
        """Create or update a borrower node keyed by SSN last 4."""
        with self.driver.session() as session:
            session.run(
                """
                MERGE (b:Borrower {ssn_last4: $ssn_last4})
                SET b.name = $name,
                    b.fico = $fico,
                    b.annual_income = $annual_income
                """,
                name=name,
                fico=fico,
                ssn_last4=ssn_last4,
                annual_income=annual_income,
            )

    def add_industry(
        self,
        *,
        name: str,
        risk_profile: str,
        default_rate: float,
    ) -> None:
        """Create or update an industry node with risk metadata."""
        with self.driver.session() as session:
            session.run(
                """
                MERGE (i:Industry {name: $name})
                SET i.risk_profile = $risk_profile,
                    i.default_rate = $default_rate
                """,
                name=name,
                risk_profile=risk_profile,
                default_rate=default_rate,
            )

    def add_company(
        self,
        *,
        name: str,
        industry: str,
        founded: int | None = None,
        employee_count: int | None = None,
    ) -> None:
        """Create company node and ensure IN_INDUSTRY relationship exists."""
        with self.driver.session() as session:
            session.run(
                """
                MERGE (c:Company {name: $name})
                SET c.founded = $founded,
                    c.employee_count = $employee_count
                MERGE (i:Industry {name: $industry})
                MERGE (c)-[:IN_INDUSTRY]->(i)
                """,
                name=name,
                industry=industry,
                founded=founded,
                employee_count=employee_count,
            )

    def add_property(
        self,
        *,
        address: str,
        value: float,
        state: str,
        property_type: str = "single_family",
    ) -> None:
        """Create property and state nodes, then link property to state."""
        with self.driver.session() as session:
            session.run(
                """
                MERGE (p:Property {address: $address})
                SET p.value = $value,
                    p.property_type = $property_type
                MERGE (s:State {name: $state})
                MERGE (p)-[:LOCATED_IN]->(s)
                """,
                address=address,
                value=value,
                state=state,
                property_type=property_type,
            )

    def add_regulation(
        self,
        *,
        code: str,
        name: str,
        jurisdiction: str,
        description: str,
        severity: str = "INFO",
    ) -> None:
        """Create or update regulation node."""
        with self.driver.session() as session:
            session.run(
                """
                MERGE (r:Regulation {code: $code})
                SET r.name = $name,
                    r.jurisdiction = $jurisdiction,
                    r.description = $description,
                    r.severity = $severity
                """,
                code=code,
                name=name,
                jurisdiction=jurisdiction.lower(),
                description=description,
                severity=severity,
            )

    def add_loan(
        self,
        *,
        loan_id: str,
        ssn_last4: str,
        amount: float,
        status: str,
        outcome: str,
        address: str,
        year: int,
    ) -> None:
        """Create a loan and link it to borrower and property."""
        with self.driver.session() as session:
            session.run(
                """
                MATCH (b:Borrower {ssn_last4: $ssn_last4})
                MATCH (p:Property {address: $address})
                MERGE (l:Loan {loan_id: $loan_id})
                SET l.amount = $amount,
                    l.status = $status,
                    l.outcome = $outcome,
                    l.year = $year
                MERGE (b)-[:HAS_LOAN]->(l)
                MERGE (l)-[:SECURED_BY]->(p)
                """,
                loan_id=loan_id,
                ssn_last4=ssn_last4,
                amount=amount,
                status=status,
                outcome=outcome,
                address=address,
                year=year,
            )

    # ----------------------------
    # Relationship methods
    # ----------------------------
    def link_borrower_employer(self, *, ssn_last4: str, company_name: str) -> None:
        """Create WORKS_AT relationship between borrower and company."""
        with self.driver.session() as session:
            session.run(
                """
                MATCH (b:Borrower {ssn_last4: $ssn_last4})
                MATCH (c:Company {name: $company_name})
                MERGE (b)-[:WORKS_AT]->(c)
                """,
                ssn_last4=ssn_last4,
                company_name=company_name,
            )

    def link_state_regulation(self, *, state: str, regulation_code: str) -> None:
        """Attach a regulation to a state via GOVErNED_BY edge."""
        with self.driver.session() as session:
            session.run(
                """
                MERGE (s:State {name: $state})
                MATCH (r:Regulation {code: $regulation_code})
                MERGE (s)-[:GOVERNED_BY]->(r)
                """,
                state=state,
                regulation_code=regulation_code,
            )

    # ----------------------------
    # Query methods
    # ----------------------------
    def get_borrower_risk_context(self, ssn_last4: str) -> dict:
        """Traverse Borrower -> Employer -> Industry plus loan/property/regulations."""
        with self.driver.session() as session:
            row = session.run(
                """
                MATCH (b:Borrower {ssn_last4: $ssn_last4})
                OPTIONAL MATCH (b)-[:WORKS_AT]->(c:Company)-[:IN_INDUSTRY]->(i:Industry)
                OPTIONAL MATCH (b)-[:HAS_LOAN]->(l:Loan)-[:SECURED_BY]->(p:Property)-[:LOCATED_IN]->(s:State)
                OPTIONAL MATCH (s)-[:GOVERNED_BY]->(r:Regulation)
                RETURN b, c, i,
                       collect(DISTINCT l) AS loans,
                       collect(DISTINCT p) AS properties,
                       collect(DISTINCT s) AS states,
                       collect(DISTINCT r) AS regulations
                """,
                ssn_last4=ssn_last4,
            ).single()

            if not row:
                return {"error": f"Borrower not found: {ssn_last4}"}

            loans = [dict(n) for n in row["loans"] if n is not None]
            defaults = sum(1 for loan in loans if loan.get("outcome") == "defaulted")
            total_loans = len(loans)
            borrower = dict(row["b"]) if row["b"] else None
            industry = dict(row["i"]) if row["i"] else None

            return {
                "borrower": borrower,
                "employer": dict(row["c"]) if row["c"] else None,
                "industry": industry,
                "industry_risk_profile": industry.get("risk_profile") if industry else None,
                "industry_default_rate": industry.get("default_rate") if industry else None,
                "loans": loans,
                "loan_summary": {
                    "total_loans": total_loans,
                    "defaulted_loans": defaults,
                    "historical_default_ratio": round(defaults / total_loans, 4) if total_loans else 0.0,
                },
                "properties": [dict(n) for n in row["properties"] if n is not None],
                "states": [dict(n) for n in row["states"] if n is not None],
                "regulations": [dict(n) for n in row["regulations"] if n is not None],
            }

    def find_similar_loans(self, industry: str, min_fico: int = 0, limit: int = 10) -> dict:
        """Return historical loans tied to borrowers in the same industry."""
        with self.driver.session() as session:
            rows = list(
                session.run(
                    """
                    MATCH (i:Industry {name: $industry})<-[:IN_INDUSTRY]-(c:Company)<-[:WORKS_AT]-(b:Borrower)
                    MATCH (b)-[:HAS_LOAN]->(l:Loan)
                    WHERE b.fico >= $min_fico
                    RETURN i.name AS industry,
                           b.name AS borrower_name,
                           b.ssn_last4 AS ssn_last4,
                           b.fico AS fico,
                           c.name AS company,
                           l.loan_id AS loan_id,
                           l.amount AS amount,
                           l.status AS status,
                           l.outcome AS outcome,
                           l.year AS year
                    ORDER BY l.year DESC, l.amount DESC
                    LIMIT $limit
                    """,
                    industry=industry,
                    min_fico=min_fico,
                    limit=limit,
                )
            )

            loans = [dict(row) for row in rows]
            defaults = sum(1 for loan in loans if loan.get("outcome") == "defaulted")
            approved = sum(1 for loan in loans if loan.get("outcome") == "approved")

            return {
                "industry": industry,
                "min_fico": min_fico,
                "count": len(loans),
                "summary": {
                    "approved": approved,
                    "defaulted": defaults,
                    "default_ratio": round(defaults / len(loans), 4) if loans else 0.0,
                },
                "loans": loans,
            }

    def get_state_regulations(self, state: str) -> dict:
        """Return state and federal regulations applicable to a state."""
        jurisdiction = state.lower()
        with self.driver.session() as session:
            rows = list(
                session.run(
                    """
                    MATCH (s:State {name: $state})-[:GOVERNED_BY]->(r:Regulation)
                    WHERE r.jurisdiction IN [$jurisdiction, "federal"]
                    RETURN s.name AS state,
                           r.code AS code,
                           r.name AS name,
                           r.jurisdiction AS jurisdiction,
                           r.description AS description,
                           r.severity AS severity
                    ORDER BY r.jurisdiction, r.code
                    """,
                    state=state,
                    jurisdiction=jurisdiction,
                )
            )

            return {
                "state": state,
                "count": len(rows),
                "regulations": [dict(row) for row in rows],
            }
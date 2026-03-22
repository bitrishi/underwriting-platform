"""Seed script for underwriting Neo4j knowledge graph sample data."""

from __future__ import annotations

from src.config.settings import settings
from src.graph.knowledge_graph import UnderwritingGraph


def seed_graph(graph: UnderwritingGraph) -> None:
    """Populate the graph with sample entities and outcomes."""
    graph.clear_graph()

    industries = [
        {"name": "energy", "risk_profile": "MEDIUM", "default_rate": 0.06},
        {"name": "healthcare", "risk_profile": "LOW", "default_rate": 0.03},
        {"name": "cryptocurrency", "risk_profile": "HIGH", "default_rate": 0.18},
    ]
    for industry in industries:
        graph.add_industry(**industry)

    companies = [
        {"name": "Lone Star Drilling", "industry": "energy", "founded": 2010, "employee_count": 220},
        {"name": "Austin Health Partners", "industry": "healthcare", "founded": 2003, "employee_count": 1300},
        {"name": "BlockNova Labs", "industry": "cryptocurrency", "founded": 2019, "employee_count": 75},
        {"name": "Metro Medical Group", "industry": "healthcare", "founded": 1998, "employee_count": 900},
    ]
    for company in companies:
        graph.add_company(**company)

    regulations = [
        {
            "code": "TRID-01",
            "name": "TRID Disclosure Rule",
            "jurisdiction": "federal",
            "description": "Timely Loan Estimate and Closing Disclosure requirements.",
            "severity": "CRITICAL",
        },
        {
            "code": "TILA-01",
            "name": "Truth in Lending Act",
            "jurisdiction": "federal",
            "description": "APR and credit terms disclosure requirements.",
            "severity": "CRITICAL",
        },
        {
            "code": "TX-HOMESTEAD-01",
            "name": "Texas Homestead Cash-Out Rule",
            "jurisdiction": "texas",
            "description": "Limits and disclosures for Texas cash-out lending.",
            "severity": "WARNING",
        },
    ]
    for regulation in regulations:
        graph.add_regulation(**regulation)

    graph.link_state_regulation(state="Texas", regulation_code="TRID-01")
    graph.link_state_regulation(state="Texas", regulation_code="TILA-01")
    graph.link_state_regulation(state="Texas", regulation_code="TX-HOMESTEAD-01")

    borrowers = [
        {
            "name": "Alicia Cole",
            "fico": 742,
            "ssn_last4": "1001",
            "annual_income": 148000,
            "company": "Austin Health Partners",
            "address": "100 Cedar St, Austin, TX",
            "value": 520000,
            "loan_id": "LN-1001",
            "amount": 390000,
            "status": "closed",
            "outcome": "approved",
            "year": 2022,
        },
        {
            "name": "Brandon Nash",
            "fico": 681,
            "ssn_last4": "1002",
            "annual_income": 104000,
            "company": "Lone Star Drilling",
            "address": "200 Oak St, Dallas, TX",
            "value": 430000,
            "loan_id": "LN-1002",
            "amount": 355000,
            "status": "closed",
            "outcome": "approved",
            "year": 2021,
        },
        {
            "name": "Carmen Ruiz",
            "fico": 655,
            "ssn_last4": "1003",
            "annual_income": 96000,
            "company": "BlockNova Labs",
            "address": "300 Pine St, Houston, TX",
            "value": 410000,
            "loan_id": "LN-1003",
            "amount": 340000,
            "status": "closed",
            "outcome": "defaulted",
            "year": 2020,
        },
        {
            "name": "Dev Patel",
            "fico": 701,
            "ssn_last4": "1004",
            "annual_income": 121000,
            "company": "Metro Medical Group",
            "address": "400 Elm St, Plano, TX",
            "value": 450000,
            "loan_id": "LN-1004",
            "amount": 320000,
            "status": "closed",
            "outcome": "approved",
            "year": 2023,
        },
        {
            "name": "Emma Stone",
            "fico": 618,
            "ssn_last4": "1005",
            "annual_income": 88000,
            "company": "BlockNova Labs",
            "address": "500 Maple St, Austin, TX",
            "value": 380000,
            "loan_id": "LN-1005",
            "amount": 330000,
            "status": "closed",
            "outcome": "defaulted",
            "year": 2022,
        },
        {
            "name": "Farah Khan",
            "fico": 728,
            "ssn_last4": "1006",
            "annual_income": 139000,
            "company": "Austin Health Partners",
            "address": "600 Walnut St, Austin, TX",
            "value": 610000,
            "loan_id": "LN-1006",
            "amount": 440000,
            "status": "closed",
            "outcome": "approved",
            "year": 2024,
        },
    ]

    for borrower in borrowers:
        graph.add_borrower(
            name=borrower["name"],
            fico=borrower["fico"],
            ssn_last4=borrower["ssn_last4"],
            annual_income=borrower["annual_income"],
        )
        graph.add_property(
            address=borrower["address"],
            value=borrower["value"],
            state="Texas",
            property_type="single_family",
        )
        graph.link_borrower_employer(
            ssn_last4=borrower["ssn_last4"],
            company_name=borrower["company"],
        )
        graph.add_loan(
            loan_id=borrower["loan_id"],
            ssn_last4=borrower["ssn_last4"],
            amount=borrower["amount"],
            status=borrower["status"],
            outcome=borrower["outcome"],
            address=borrower["address"],
            year=borrower["year"],
        )


def main() -> None:
    graph = UnderwritingGraph(
        settings.neo4j_uri,
        settings.neo4j_user,
        settings.neo4j_password,
    )
    try:
        if not graph.verify_connection():
            raise RuntimeError("Neo4j connection verification failed")
        seed_graph(graph)
        print("Seed complete: sample underwriting graph created.")
    finally:
        graph.close()


if __name__ == "__main__":
    main()

from langchain_core.tools import tool
from datetime import datetime


@tool
def pull_borrower_data(app_id: str) -> dict:
    """Pull borrower profile from the loan origination system.
    
    Use this to get basic borrower information including
    income, debt, loan amount, and property details.
    
    Args:
        app_id: Loan application ID from the origination system
        
    Returns:
        Borrower profile with income, debt, loan, property data
    """
    # SIMULATED — in production, calls Camelot API
    applications = {
        "APP-001": {
            "name": "Alice Strong",
            "ssn_last_four": "1234",
            "annual_income": 120000,
            "monthly_debt": 2400,
            "loan_amount": 350000,
            "property_value": 440000,
            "property_state": "texas",
        },
        "APP-002": {
            "name": "Bob Risky",
            "ssn_last_four": "5678",
            "annual_income": 55000,
            "monthly_debt": 2200,
            "loan_amount": 280000,
            "property_value": 290000,
            "property_state": "california",
        },
    }
    
    data = applications.get(app_id)
    if not data:
        return {"error": f"Application {app_id} not found"}
    return data


@tool
def pull_credit_report(ssn_last_four: str) -> dict:
    """Pull credit report from the credit bureau.
    
    Use this to get FICO score, delinquency history,
    and credit account details.
    
    Args:
        ssn_last_four: Last 4 digits of borrower's SSN
        
    Returns:
        Credit report with FICO, delinquencies, accounts
    """
    # SIMULATED — in production, calls credit bureau API
    reports = {
        "1234": {
            "fico_score": 740,
            "delinquencies": 0,
            "open_accounts": 8,
            "credit_history_years": 12,
            "tier": "EXCELLENT",
        },
        "5678": {
            "fico_score": 620,
            "delinquencies": 3,
            "open_accounts": 12,
            "credit_history_years": 4,
            "tier": "BELOW_MINIMUM",
        },
    }
    
    data = reports.get(ssn_last_four)
    if not data:
        return {"error": f"No credit report for SSN ***-**-{ssn_last_four}"}
    return data


@tool
def pull_employment_history(ssn_last_four: str) -> dict:
    """Pull employment verification from employment database.
    
    Use this to verify current employer, tenure, and
    employment type.
    
    Args:
        ssn_last_four: Last 4 digits of borrower's SSN
        
    Returns:
        Employment record with employer, tenure, type
    """
    # SIMULATED — in production, calls employment verification API
    records = {
        "1234": {
            "employer": "TechCorp Inc",
            "position": "Senior Engineer",
            "years_at_current": 5,
            "employment_type": "FULL_TIME",
            "verified": True,
        },
        "5678": {
            "employer": "StartupXYZ",
            "position": "Junior Developer",
            "years_at_current": 0.5,
            "employment_type": "FULL_TIME",
            "verified": True,
        },
    }
    
    data = records.get(ssn_last_four)
    if not data:
        return {"error": f"No employment record for ***-**-{ssn_last_four}"}
    return data
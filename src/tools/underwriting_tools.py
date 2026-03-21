from langchain_core.tools import tool

@tool
def calculate_dti(annual_income: float, monthly_debt: float) -> dict:
    """Calculate the debt-to-income ratio for underwriting
    Use this tool whenever you need to evaluate the bowrrors debt burden against their asset
    Args:
    annual_income: Borrower's annual income in dollars
    monthly_debt: Borrower's total monthly debt payments in dollars

    Returns:
    DTI percentage, threshold, pass/fail status
    """
    if annual_income <= 0:
        raise ValueError("annual_income must be positive")

    dti = (monthly_debt * 12) / annual_income * 100
    return {
        "dti": dti,
        "threshold": 43,
        "pass": dti <= 43,
        "detail": f"DTI {dti:.1f}% {'<=' if dti <= 43 else '>'} 43% threshold"
    }


@tool
def calculate_ltv(loan_amount: float, property_value: float) -> dict:
    """Calculate Loan-to-Value ratio for mortgage underwriting.
    
    Use this tool to assess how much of the property value
    is being financed.
    
    Args:
        loan_amount: Requested loan amount in USD
        property_value: Appraised property value in USD
        
    Returns:
        LTV percentage, PMI requirement, and threshold status
    """
    if property_value <= 0:
        raise ValueError("property_value must be positive")

    ltv = loan_amount / property_value * 100
    return {
        "ltv": round(ltv, 2),
        "threshold": 80.0,
        "requires_pmi": ltv > 80,
        "pass": ltv <= 95,
        "detail": f"LTV {ltv:.1f}% — {'PMI required' if ltv > 80 else 'No PMI'}"
    }


@tool
def check_fico_eligibility(fico_score: int) -> dict:
    """Check if a FICO score meets minimum underwriting requirements.
    
    Use this tool to evaluate creditworthiness against
    lending thresholds.
    
    Args:
        fico_score: Borrower's FICO credit score (300-850)
        
    Returns:
        Eligibility status, risk tier, and threshold details
    """
    if fico_score < 300 or fico_score > 850:
        raise ValueError("fico_score must be between 300 and 850")

    if fico_score >= 740:
        tier = "EXCELLENT"
    elif fico_score >= 700:
        tier = "GOOD"
    elif fico_score >= 680:
        tier = "ACCEPTABLE"
    else:
        tier = "BELOW_MINIMUM"
    
    return {
        "fico": fico_score,
        "minimum_threshold": 680,
        "tier": tier,
        "eligible": fico_score >= 680,
        "detail": f"FICO {fico_score} — {tier}"
    }

    def check_employment_stability(years: float) -> dict:
        """Evaluate employment stability for underwriting.
        
        Use this tool to assess the risk associated with the
        borrower's employment history.
        
        Args:
            years: Number of years in current employment
            
        Returns:
            Stability status, risk level, and threshold information
        """
        if years >= 5:
            stability = "HIGHLY_STABLE"
        elif years >= 2:
            stability = "STABLE"
        elif years >= 1:
            stability = "MARGINALLY_STABLE"
        else:
            stability = "UNSTABLE"
        
        return {
            "employment_years": years,
            "stability": stability,
            "threshold": 2,
            "meets_threshold": years >= 2,
            "detail": f"Employment {years} years — {stability}"
        }       
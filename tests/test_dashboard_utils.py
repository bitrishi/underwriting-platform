from src.dashboard.utils import build_pdf_report, get_risk_color, get_risk_label


def test_risk_color_thresholds():
    assert get_risk_color(20) == "#15803d"
    assert get_risk_color(55) == "#ca8a04"
    assert get_risk_color(90) == "#b91c1c"
    assert get_risk_label(20) == "Low"
    assert get_risk_label(55) == "Moderate"
    assert get_risk_label(90) == "High"


def test_pdf_report_generation_returns_bytes():
    payload = {
        "application_id": "APP-001",
        "evaluated_at": "2026-04-05T12:00:00Z",
        "borrower_data": {"fico": 740, "income": 120000, "dti": 0.31},
        "decision": {"decision": "APPROVED", "confidence": 0.94, "risk_level": "LOW", "reasons": ["Strong profile"]},
        "risk_score": 28,
        "agent_reports": [{"agent_name": "FetchData", "summary": "Done", "details": {}, "status": "completed"}],
        "audit_trail": [{"step": "submission_received", "status": "completed", "timestamp": "2026-04-05T12:00:00Z", "detail": "Received payload"}],
    }

    pdf = build_pdf_report(payload)

    assert isinstance(pdf, bytes)
    assert pdf.startswith(b"%PDF")
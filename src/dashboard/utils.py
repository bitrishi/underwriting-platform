"""Helpers for the Streamlit underwriting dashboard."""

from __future__ import annotations

from io import BytesIO
import os
from typing import Any

import requests
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer


API_BASE_URL = os.environ.get("UNDERWRITING_API_URL", "http://localhost:8000")


def get_risk_color(risk_score: int) -> str:
    if risk_score < 40:
        return "#15803d"
    if risk_score <= 70:
        return "#ca8a04"
    return "#b91c1c"


def get_risk_label(risk_score: int) -> str:
    if risk_score < 40:
        return "Low"
    if risk_score <= 70:
        return "Moderate"
    return "High"


def submit_evaluation(application: dict[str, Any]) -> dict[str, Any]:
    response = requests.post(
        f"{API_BASE_URL}/evaluate",
        json=application,
        timeout=60,
    )
    response.raise_for_status()
    return response.json()


def get_job_status(job_id: str) -> dict[str, Any]:
    response = requests.get(
        f"{API_BASE_URL}/status",
        params={"job_id": job_id},
        timeout=30,
    )
    response.raise_for_status()
    return response.json()


def get_job_result(job_id: str) -> dict[str, Any] | None:
    response = requests.get(
        f"{API_BASE_URL}/result",
        params={"job_id": job_id},
        timeout=30,
    )
    if response.status_code == 202:
        return None
    response.raise_for_status()
    payload = response.json()
    return payload["result"]


def get_evaluation_history(application_id: str) -> dict[str, Any]:
    response = requests.get(
        f"{API_BASE_URL}/evaluate/history",
        params={"application_id": application_id},
        timeout=30,
    )
    response.raise_for_status()
    return response.json()


def build_pdf_report(evaluation: dict[str, Any]) -> bytes:
    buffer = BytesIO()
    document = SimpleDocTemplate(buffer, pagesize=letter)
    styles = getSampleStyleSheet()

    risk_score = int(evaluation.get("risk_score", 0))
    color_hex = get_risk_color(risk_score)
    risk_color = colors.HexColor(color_hex)

    story = [
        Paragraph(f"Underwriting Evaluation Report: {evaluation.get('application_id', 'UNKNOWN')}", styles["Title"]),
        Spacer(1, 12),
        Paragraph(f"Evaluated At: {evaluation.get('evaluated_at', '')}", styles["BodyText"]),
        Paragraph(f"Recommendation: {evaluation.get('recommendation', 'UNKNOWN')}", styles["Heading2"]),
        Paragraph(
            f"Risk Score: <font color='{color_hex}'>{risk_score} ({get_risk_label(risk_score)})</font>",
            styles["Heading2"],
        ),
        Spacer(1, 8),
        Paragraph("Borrower Data", styles["Heading2"]),
    ]

    for key, value in evaluation.get("borrower_data", {}).items():
        story.append(Paragraph(f"{key}: {value}", styles["BodyText"]))

    story.extend([
        Spacer(1, 8),
        Paragraph("Decision", styles["Heading2"]),
    ])

    for key, value in evaluation.get("decision", {}).items():
        story.append(Paragraph(f"{key}: {value}", styles["BodyText"]))

    story.extend([
        Spacer(1, 8),
        Paragraph("Agent Reports", styles["Heading2"]),
    ])
    for report in evaluation.get("agent_reports", []):
        story.append(Paragraph(f"{report['agent_name']}: {report['summary']}", styles["BodyText"]))

    story.extend([
        Spacer(1, 8),
        Paragraph("Audit Trail", styles["Heading2"]),
    ])
    for event in evaluation.get("audit_trail", []):
        story.append(Paragraph(f"{event['step']} [{event['status']}]: {event['detail']}", styles["BodyText"]))

    document.build(story)
    pdf_bytes = buffer.getvalue()
    buffer.close()
    return pdf_bytes

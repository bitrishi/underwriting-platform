"""Create and publish a Bedrock guardrail for underwriting workflows."""

from __future__ import annotations

from datetime import UTC, datetime

import boto3


def create_underwriting_guardrail(region: str = "us-east-1") -> dict[str, str]:
    client = boto3.client("bedrock", region_name=region)

    name = f"underwriting-guardrail-{datetime.now(UTC).strftime('%Y%m%d-%H%M%S')}"

    content_filters = [
        {"type": "SEXUAL", "inputStrength": "HIGH", "outputStrength": "HIGH"},
        {"type": "VIOLENCE", "inputStrength": "HIGH", "outputStrength": "HIGH"},
        {"type": "HATE", "inputStrength": "HIGH", "outputStrength": "HIGH"},
        {"type": "INSULTS", "inputStrength": "HIGH", "outputStrength": "HIGH"},
        {"type": "MISCONDUCT", "inputStrength": "HIGH", "outputStrength": "HIGH"},
        # Bedrock currently requires outputStrength NONE for PROMPT_ATTACK.
        {"type": "PROMPT_ATTACK", "inputStrength": "HIGH", "outputStrength": "NONE"},
    ]

    topics = [
        {
            "name": "NoPersonalFinancialAdvice",
            "definition": "Blocks personalized financial advice in underwriting workflows.",
            "examples": [
                "Should I refinance now based on my income?",
                "Tell me what loan amount I should personally take.",
            ],
            "type": "DENY",
        },
        {
            "name": "NoOffTopicRequests",
            "definition": "Blocks requests unrelated to mortgage underwriting.",
            "examples": ["Write my dating profile", "Plan a vacation itinerary"],
            "type": "DENY",
        },
        {
            "name": "NoLendingDiscrimination",
            "definition": "Blocks discriminatory lending guidance based on protected attributes.",
            "examples": ["Reject this borrower because of race", "Approve only one religion"],
            "type": "DENY",
        },
    ]

    pii_entities = [
        {"type": "US_SOCIAL_SECURITY_NUMBER", "action": "ANONYMIZE"},
        {"type": "CREDIT_DEBIT_CARD_NUMBER", "action": "ANONYMIZE"},
        {"type": "PHONE", "action": "ANONYMIZE"},
    ]

    word_filters = [
        {"text": "guaranteed approval", "inputAction": "BLOCK", "outputAction": "BLOCK"},
        {"text": "skip income verification", "inputAction": "BLOCK", "outputAction": "BLOCK"},
        {"text": "racial quota lending", "inputAction": "BLOCK", "outputAction": "BLOCK"},
    ]

    response = client.create_guardrail(
        name=name,
        description="Guardrail for mortgage underwriting agent workflows.",
        blockedInputMessaging="Request blocked by underwriting safety policy.",
        blockedOutputsMessaging="Response blocked by underwriting safety policy.",
        contentPolicyConfig={"filtersConfig": content_filters},
        topicPolicyConfig={"topicsConfig": topics},
        sensitiveInformationPolicyConfig={"piiEntitiesConfig": pii_entities},
        wordPolicyConfig={"wordsConfig": word_filters},
        contextualGroundingPolicyConfig={
            "filtersConfig": [
                {"type": "GROUNDING", "threshold": 0.85, "action": "BLOCK"},
                {"type": "RELEVANCE", "threshold": 0.80, "action": "BLOCK"},
            ]
        },
    )

    guardrail_id = response["guardrailId"]
    draft_version = response["version"]

    version_response = client.create_guardrail_version(guardrailIdentifier=guardrail_id)
    published_version = version_response["version"]

    return {
        "name": name,
        "guardrail_id": guardrail_id,
        "draft_version": draft_version,
        "published_version": published_version,
    }


if __name__ == "__main__":
    created = create_underwriting_guardrail()
    print(f"GUARDRAIL_NAME={created['name']}")
    print(f"GUARDRAIL_ID={created['guardrail_id']}")
    print(f"GUARDRAIL_DRAFT_VERSION={created['draft_version']}")
    print(f"GUARDRAIL_PUBLISHED_VERSION={created['published_version']}")

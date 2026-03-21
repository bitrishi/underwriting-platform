import os
import sys

import numpy as np
from langchain_aws import BedrockEmbeddings

# Ensure repository root is importable when run directly as a script.
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from src.config.settings import settings


def create_embeddings_client() -> BedrockEmbeddings:
    """Create Bedrock embeddings client for similarity testing."""
    return BedrockEmbeddings(
        model_id="amazon.titan-embed-text-v2:0",
        region_name=settings.aws_region,
    )


def cosine_similarity(vec_a: list[float], vec_b: list[float]) -> float:
    """Compute cosine similarity between two embedding vectors."""
    a = np.array(vec_a, dtype=float)
    b = np.array(vec_b, dtype=float)
    denominator = np.linalg.norm(a) * np.linalg.norm(b)
    if denominator == 0:
        raise ValueError("Cannot compute cosine similarity for zero-length vector.")
    return float(np.dot(a, b) / denominator)


def main() -> None:
    embeddings = create_embeddings_client()

    similar_q1 = "What are the debt-to-income limits for mortgage approval?"
    similar_q2 = "What are the DTI requirements to qualify for a home loan?"

    unrelated_q1 = "What are the debt-to-income limits for mortgage approval?"
    unrelated_q2 = "How do I reset my smartphone to factory settings?"

    similar_vec_1 = embeddings.embed_query(similar_q1)
    similar_vec_2 = embeddings.embed_query(similar_q2)
    unrelated_vec_1 = embeddings.embed_query(unrelated_q1)
    unrelated_vec_2 = embeddings.embed_query(unrelated_q2)

    similar_score = cosine_similarity(similar_vec_1, similar_vec_2)
    unrelated_score = cosine_similarity(unrelated_vec_1, unrelated_vec_2)

    print("Cosine similarity test results")
    print("=" * 40)
    print(f"Semantically similar pair score: {similar_score:.4f}")
    print(f"Unrelated pair score:          {unrelated_score:.4f}")

    similar_ok = similar_score > 0.8
    unrelated_ok = unrelated_score < 0.3

    print("\nVerification")
    print("=" * 40)
    print(f"Similar > 0.8:   {'PASS' if similar_ok else 'FAIL'}")
    print(f"Unrelated < 0.3: {'PASS' if unrelated_ok else 'FAIL'}")

    assert similar_ok, f"Expected similar score > 0.8, got {similar_score:.4f}"
    assert unrelated_ok, f"Expected unrelated score < 0.3, got {unrelated_score:.4f}"


if __name__ == "__main__":
    main()

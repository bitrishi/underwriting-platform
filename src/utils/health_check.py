"""Dependency health checks for the underwriting pipeline.

The top-level :func:`check_all_dependencies` is designed to be called from
an ECS health-check endpoint (e.g. ``GET /health``).

Status levels
-------------
``healthy``  — all checks passed.
``degraded`` — at least one non-critical dependency returned a warning;
               the pipeline can still run with reduced capability.
``unhealthy`` — at least one critical dependency is unreachable; the pipeline
                should not accept new evaluations.

Circuit-breaker status
----------------------
The check also reads the current state of every circuit breaker registered
in ``ALL_BREAKERS`` so operators can see which external services are tripped.
"""

from __future__ import annotations

import json
import logging
import time
import urllib.request
from typing import Any

logger = logging.getLogger(__name__)


# ── Individual dependency probes ──────────────────────────────────────────────


def _check_bedrock() -> dict[str, Any]:
    """Probe AWS Bedrock by listing foundation models (read-only, no tokens used)."""
    try:
        import boto3  # type: ignore[import]
        from botocore.exceptions import BotoCoreError, ClientError  # type: ignore[import]

        from src.config.settings import settings

        t0 = time.perf_counter()
        client = boto3.client("bedrock", region_name=settings.aws_region)
        client.list_foundation_models(maxResults=1)
        latency_ms = round((time.perf_counter() - t0) * 1000, 2)
        return {"status": "healthy", "latency_ms": latency_ms}
    except Exception as exc:
        logger.warning("[health_check] bedrock probe failed: %s", exc)
        return {"status": "unhealthy", "error": str(exc)}


def _check_neo4j() -> dict[str, Any]:
    """Probe Neo4j with a driver connectivity verification (no query executed)."""
    try:
        from neo4j import GraphDatabase  # type: ignore[import]

        from src.config.settings import settings

        t0 = time.perf_counter()
        driver = GraphDatabase.driver(
            settings.neo4j_uri,
            auth=(settings.neo4j_user, settings.neo4j_password),
        )
        driver.verify_connectivity()
        driver.close()
        latency_ms = round((time.perf_counter() - t0) * 1000, 2)
        return {"status": "healthy", "latency_ms": latency_ms}
    except Exception as exc:
        logger.warning("[health_check] neo4j probe failed: %s", exc)
        return {"status": "unhealthy", "error": str(exc)}


def _check_faiss() -> dict[str, Any]:
    """Verify the primary FAISS vector-store index file is readable on disk."""
    try:
        from pathlib import Path

        index_path = Path("data/vectorstore/index.faiss")
        if index_path.exists():
            return {"status": "healthy", "index_path": str(index_path)}
        return {
            "status": "degraded",
            "detail": "FAISS index not found — will rebuild on first query.",
        }
    except Exception as exc:
        logger.warning("[health_check] faiss probe failed: %s", exc)
        return {"status": "unhealthy", "error": str(exc)}


def _check_opensearch() -> dict[str, Any]:
    """Probe OpenSearch cluster health endpoint.

    Requires the ``OPENSEARCH_ENDPOINT`` environment variable.  If it is not
    set the check is marked ``degraded`` (not ``unhealthy``) because
    OpenSearch is not a critical dependency for the default pipeline path.
    """
    try:
        import os

        endpoint = os.environ.get("OPENSEARCH_ENDPOINT", "").rstrip("/")
        if not endpoint:
            return {
                "status": "degraded",
                "detail": "OPENSEARCH_ENDPOINT not configured.",
            }

        url = f"{endpoint}/_cluster/health"
        t0 = time.perf_counter()
        with urllib.request.urlopen(url, timeout=5) as resp:  # noqa: S310
            body: dict[str, Any] = json.loads(resp.read())
        latency_ms = round((time.perf_counter() - t0) * 1000, 2)

        cluster_status = body.get("status", "unknown")
        if cluster_status == "red":
            return {"status": "unhealthy", "cluster_status": cluster_status, "latency_ms": latency_ms}
        if cluster_status == "yellow":
            return {"status": "degraded", "cluster_status": cluster_status, "latency_ms": latency_ms}
        return {"status": "healthy", "cluster_status": cluster_status, "latency_ms": latency_ms}

    except Exception as exc:
        logger.warning("[health_check] opensearch probe failed: %s", exc)
        return {"status": "unhealthy", "error": str(exc)}


def _check_circuit_breakers() -> dict[str, Any]:
    """Read status snapshots for all registered circuit breakers.

    Returns a dict of ``{breaker_name: status_dict}`` so the health endpoint
    can surface which services have been tripped without running live probes.
    """
    try:
        from src.utils.circuit_breaker import ALL_BREAKERS

        states = {name: breaker.status() for name, breaker in ALL_BREAKERS.items()}
        any_open = any(s["state"] != "CLOSED" for s in states.values())
        return {
            "status": "degraded" if any_open else "healthy",
            "breakers": states,
        }
    except Exception as exc:
        logger.warning("[health_check] circuit breaker status failed: %s", exc)
        return {"status": "degraded", "error": str(exc)}


# ── Aggregated health check ───────────────────────────────────────────────────


def check_all_dependencies() -> dict[str, Any]:
    """Run health probes for all pipeline dependencies.

    Returns:
        dict with:
        - ``status``: ``"healthy"`` | ``"degraded"`` | ``"unhealthy"``
        - ``dependencies``: per-dependency status dicts
        - ``circuit_breakers``: circuit-breaker state snapshot
        - ``check_duration_ms``: total probe wall time

    The top-level ``status`` is:
    - ``"unhealthy"`` if *any* dependency reports ``"unhealthy"``
    - ``"degraded"``  if *any* dependency reports ``"degraded"`` (but none
      are ``"unhealthy"``)
    - ``"healthy"``   otherwise

    Designed for use as an ECS health-check endpoint::

        @app.get("/health")
        def health():
            return check_all_dependencies()
    """
    t0 = time.perf_counter()

    dependencies: dict[str, Any] = {
        "bedrock": _check_bedrock(),
        "neo4j": _check_neo4j(),
        "faiss": _check_faiss(),
        "opensearch": _check_opensearch(),
    }
    circuit_breakers = _check_circuit_breakers()

    statuses = {v["status"] for v in dependencies.values()}
    if "unhealthy" in statuses:
        overall = "unhealthy"
    elif "degraded" in statuses or circuit_breakers.get("status") == "degraded":
        overall = "degraded"
    else:
        overall = "healthy"

    return {
        "status": overall,
        "dependencies": dependencies,
        "circuit_breakers": circuit_breakers,
        "check_duration_ms": round((time.perf_counter() - t0) * 1000, 2),
    }

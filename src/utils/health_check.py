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

import logging
import os
import time
import urllib.request
from typing import Any

logger = logging.getLogger(__name__)


# ── Individual dependency probes ──────────────────────────────────────────────


def _check_bedrock() -> dict[str, Any]:
    """Probe Bedrock runtime with a tiny prompt to validate invoke path."""
    try:
        from src.config.bedrock import create_llm

        llm = create_llm(task="default", max_tokens=16)
        t0 = time.perf_counter()
        llm.invoke("Reply with: ok")
        latency_ms = round((time.perf_counter() - t0) * 1000, 2)
        return {"status": "healthy", "latency_ms": latency_ms}
    except Exception as exc:
        logger.warning("[health_check] bedrock probe failed: %s", exc)
        return {"status": "unhealthy", "error": str(exc)}


def _check_neo4j() -> dict[str, Any]:
    """Probe Neo4j by running a simple read query."""
    try:
        from neo4j import GraphDatabase  # type: ignore[import]

        from src.config.settings import settings

        t0 = time.perf_counter()
        driver = GraphDatabase.driver(
            settings.neo4j_uri,
            auth=(settings.neo4j_user, settings.neo4j_password),
        )
        with driver.session() as session:
            session.run("RETURN 1 AS ok").single()
        driver.close()
        latency_ms = round((time.perf_counter() - t0) * 1000, 2)
        return {"status": "healthy", "latency_ms": latency_ms}
    except Exception as exc:
        logger.warning("[health_check] neo4j probe failed: %s", exc)
        return {"status": "unhealthy", "error": str(exc)}


def _check_faiss() -> dict[str, Any]:
    """Verify FAISS is queryable with a trivial search."""
    try:
        from src.rag.vectorstore import search_policies

        t0 = time.perf_counter()
        docs = search_policies("DTI", top_k=1)
        latency_ms = round((time.perf_counter() - t0) * 1000, 2)
        return {"status": "healthy", "latency_ms": latency_ms, "results": len(docs)}
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
        endpoint = os.environ.get("OPENSEARCH_ENDPOINT", "").rstrip("/")
        if not endpoint:
            return {
                "status": "degraded",
                "detail": "OPENSEARCH_ENDPOINT not configured.",
            }

        url = f"{endpoint}/_cluster/health"
        t0 = time.perf_counter()
        with urllib.request.urlopen(url, timeout=5) as resp:  # noqa: S310
            body = resp.read().decode("utf-8")
        latency_ms = round((time.perf_counter() - t0) * 1000, 2)

        cluster_status = "green"
        if '"status":"yellow"' in body:
            cluster_status = "yellow"
        elif '"status":"red"' in body:
            cluster_status = "red"
        if cluster_status == "red":
            return {"status": "unhealthy", "cluster_status": cluster_status, "latency_ms": latency_ms}
        if cluster_status == "yellow":
            return {"status": "degraded", "cluster_status": cluster_status, "latency_ms": latency_ms}
        return {"status": "healthy", "cluster_status": cluster_status, "latency_ms": latency_ms}

    except Exception as exc:
        logger.warning("[health_check] opensearch probe failed: %s", exc)
        return {"status": "unhealthy", "error": str(exc)}


def _check_redis() -> dict[str, Any]:
    """Ping Redis when configured; returns degraded if not configured."""
    redis_url = os.environ.get("REDIS_URL", "").strip()
    if not redis_url:
        return {"status": "degraded", "detail": "REDIS_URL not configured."}

    try:
        import redis  # type: ignore[import]

        t0 = time.perf_counter()
        client = redis.from_url(redis_url)
        pong = client.ping()
        latency_ms = round((time.perf_counter() - t0) * 1000, 2)
        return {"status": "healthy" if pong else "unhealthy", "latency_ms": latency_ms}
    except Exception as exc:
        logger.warning("[health_check] redis probe failed: %s", exc)
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
        "redis": _check_redis(),
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

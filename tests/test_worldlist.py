"""Security and validation tests for the public worldlist builder."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

from custom_components.benchmark.engine import PROFILES
from custom_components.benchmark.scoring import compute_scores


def measurement_set() -> dict:
    measurements = {
        section: {
            "count": 300,
            "min_ms": 0.5,
            "mean_ms": 1.0,
            "p50_ms": 0.8,
            "p95_ms": 1.5,
            "p99_ms": 2.5,
            "max_ms": 3.0,
            "stddev_ms": 0.2,
            "cv": 0.2,
        }
        for section in (
            "event_loop_idle",
            "event_loop_loaded",
            "state_machine",
            "event_bus",
            "service_calls",
            "template_render",
        )
    }
    measurements["service_calls"]["count"] = 200
    return measurements


def valid_payload() -> dict:
    measurements = measurement_set()
    scores = compute_scores(measurements)
    return {
        "schema": "ha_homeassistant_performance_result_v3",
        "result_id": "a" * 32,
        "timestamp": "2026-07-16T10:00:00+00:00",
        "protocol_version": "3.0.0",
        "score_version": "ha_score_v3",
        "protocol": {
            "timer_interval_ms": 20,
            "sample_counts": {
                "event_loop_idle": 300,
                "event_loop_loaded": 300,
                "state_machine": 300,
                "event_bus": 300,
                "service_calls": 200,
                "template_render": 300,
            },
            "controlled_load": {
                "batch_size": 5,
                "batch_period_ms": 20,
                "target_service_calls_s": 250,
                "state_updates": False,
            },
        },
        "profile": "standard",
        "duration_s": 15,
        "scores": scores,
        "measurements": measurements,
        "system": {
            "home_assistant_version": "2026.7.2",
            "entity_count": 500,
            "architecture": "x86_64",
        },
        "secondary": {},
        "validity": {
            "ranking_eligible": True,
            "confidence": "high",
            "warnings": [],
        },
    }


@pytest.fixture
def builder(monkeypatch):
    monkeypatch.setenv("GITHUB_REPOSITORY", "Jarnsen/test")
    monkeypatch.setenv("GITHUB_TOKEN", "test")
    path = Path(".github/scripts/build_worldlist.py")
    spec = importlib.util.spec_from_file_location("worldlist_builder", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def issue(payload: dict, *, number: int = 1) -> dict:
    return {
        "number": number,
        "html_url": f"https://github.com/Jarnsen/test/issues/{number}",
        "created_at": "2026-07-16T10:00:00Z",
        "updated_at": "2026-07-16T10:00:00Z",
        "body": f"### Anonymous benchmark JSON\n\n```json\n{json.dumps(payload)}\n```",
    }


def test_server_recalculates_reported_score(builder) -> None:
    payload = valid_payload()
    payload["scores"]["ha_performance_score"] = 10_000
    entry = builder.entry_from_issue(issue(payload))
    assert entry is not None
    assert (
        entry["score"]
        == compute_scores(payload["measurements"])["ha_performance_score"]
    )
    assert entry["reported_score_matches"] is False


def test_public_protocol_matches_standard_profile(builder) -> None:
    standard = PROFILES["standard"]
    assert builder.EXPECTED_STANDARD_PROTOCOL["sample_counts"] == {
        "event_loop_idle": standard.idle_loop_samples,
        "event_loop_loaded": standard.loaded_loop_samples,
        "state_machine": standard.state_samples,
        "event_bus": standard.event_samples,
        "service_calls": standard.service_samples,
        "template_render": standard.template_samples,
    }
    assert builder.EXPECTED_STANDARD_PROTOCOL["timer_interval_ms"] == round(
        standard.timer_interval_s * 1000
    )


def test_rejects_nonstandard_profile(builder) -> None:
    payload = valid_payload()
    payload["profile"] = "quick"
    assert builder.entry_from_issue(issue(payload)) is None


def test_rejects_insufficient_samples(builder) -> None:
    payload = valid_payload()
    payload["measurements"]["event_bus"]["count"] = 1
    assert builder.entry_from_issue(issue(payload)) is None


def test_rejects_inconsistent_percentiles(builder) -> None:
    payload = valid_payload()
    payload["measurements"]["event_bus"]["p95_ms"] = 5
    payload["measurements"]["event_bus"]["p99_ms"] = 2
    assert builder.entry_from_issue(issue(payload)) is None


def test_sanitizes_public_metadata(builder) -> None:
    payload = valid_payload()
    payload["system"]["architecture"] = "x86|malicious\nrow"
    entry = builder.entry_from_issue(issue(payload))
    assert entry is not None
    assert entry["architecture"] == "x86/malicious row"

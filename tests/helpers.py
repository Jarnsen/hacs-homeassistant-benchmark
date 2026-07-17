"""Reusable fixtures and factories for benchmark tests."""

from __future__ import annotations

import datetime as dt
from typing import Any

from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.benchmark.const import DOMAIN, RESULT_SCHEMA
from custom_components.benchmark.scoring import SCORE_VERSION


def measurement_set(value: float = 1.0, count: int = 300) -> dict[str, Any]:
    """Return a complete, internally consistent measurement set."""
    return {
        section: {
            "count": 200 if section == "service_calls" and count == 300 else count,
            "min_ms": value,
            "mean_ms": value,
            "p50_ms": value,
            "p95_ms": value,
            "p99_ms": value,
            "max_ms": value,
            "stddev_ms": value * 0.1,
            "cv": 0.1,
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


def benchmark_result(
    *,
    profile: str = "standard",
    score: int = 8000,
    ranking_eligible: bool = True,
) -> dict[str, Any]:
    """Return a representative persisted v3 benchmark result."""
    return {
        "schema": RESULT_SCHEMA,
        "result_id": "result-1",
        "timestamp": dt.datetime(2026, 1, 2, 3, 4, tzinfo=dt.UTC).isoformat(),
        "protocol_version": "3.0.0",
        "score_version": SCORE_VERSION,
        "protocol": {"sample_counts": {}},
        "profile": profile,
        "duration_s": 12.5,
        "scores": {
            "score_version": SCORE_VERSION,
            "ha_performance_score": score,
            "ha_core_score": score - 100,
            "fluidity_score": score + 100,
        },
        "measurements": measurement_set(),
        "system": {
            "home_assistant_version": "2026.7.2",
            "installation_type": "container_or_core",
            "entity_count": 400,
            "device_count": 10,
            "config_entry_count": 5,
            "recorder_loaded": True,
            "architecture": "x86_64",
            "cpu_model": "Test CPU",
            "device_model": "Test device",
            "operating_system": "Test OS",
            "python_version": "3.14.0",
            "cpu_cores_logical": 4,
            "ram_total_mb": 4096,
            "disk_free_mb": 123,
        },
        "secondary": {"restart_recovery_time_s": None},
        "validity": {
            "completed": True,
            "ranking_eligible": ranking_eligible,
            "confidence": "high",
            "warnings": [],
        },
    }


async def setup_benchmark_entry(hass, *, options: dict[str, Any] | None = None):
    """Create and load a benchmark config entry."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Home Assistant Performance Benchmark",
        unique_id=DOMAIN,
        version=2,
        options=options or {},
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry

"""Tests for the versioned scoring protocol."""

from __future__ import annotations

import math

import pytest

from custom_components.benchmark.scoring import (
    SCORE_VERSION,
    _measurement_value,
    _weighted_geometric,
    compute_scores,
    normalize_lower,
    percentile,
    summarize_samples,
    validate_measurements,
)


def measurement_set(value: float = 1.0, count: int = 300) -> dict:
    """Return a complete synthetic measurement set."""
    return {
        section: {
            "count": count,
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


def test_percentile_interpolates() -> None:
    assert percentile([0, 10], 0.5) == 5
    assert percentile([3], 0.99) == 3
    assert percentile([3, 1], -1) == 1
    assert percentile([3, 1], 2) == 3


def test_percentile_rejects_empty_input() -> None:
    with pytest.raises(ValueError, match="at least one"):
        percentile([], 0.5)


def test_sample_summary_has_long_tail_and_throughput() -> None:
    summary = summarize_samples(
        [1, 2, 3, 100],
        elapsed_s=2,
    )
    assert summary["count"] == 4
    assert summary["p50_ms"] == 2.5
    assert summary["p99_ms"] > 90
    assert summary["spikes_over_50ms"] == 1
    assert summary["throughput_ops_s"] == 2


def test_sample_summary_rejects_invalid_input() -> None:
    with pytest.raises(ValueError, match="No valid"):
        summarize_samples([math.nan, -1])


def test_sample_summary_filters_values_and_handles_zero_mean() -> None:
    summary = summarize_samples([0, 0, math.inf, "invalid"], elapsed_s=0)
    assert summary["count"] == 2
    assert summary["stddev_ms"] == 0
    assert summary["cv"] == 0
    assert "throughput_ops_s" not in summary
    assert summary["spikes_over_20ms"] == 0


def test_log_normalization_bounds() -> None:
    assert normalize_lower(0.1, 0.5, 50) == 1
    assert normalize_lower(50, 0.5, 50) == 0
    assert 0 < normalize_lower(5, 0.5, 50) < 1
    assert normalize_lower("invalid", 0.5, 50) == 0


@pytest.mark.parametrize(
    ("value", "ideal", "poor"),
    [
        (math.nan, 0.5, 50),
        (-1, 0.5, 50),
        (1, 0, 50),
        (1, 50, 50),
    ],
)
def test_log_normalization_rejects_invalid_ranges(value, ideal, poor) -> None:
    assert normalize_lower(value, ideal, poor) == 0


def test_private_scoring_guards() -> None:
    assert _weighted_geometric({}) == 0
    with pytest.raises(ValueError, match="Invalid measurement"):
        _measurement_value({"section": {"value": math.inf}}, "section", "value")


def test_fast_measurements_score_higher_than_slow() -> None:
    fast = compute_scores(measurement_set(0.4))
    slow = compute_scores(measurement_set(20))
    assert fast["score_version"] == SCORE_VERSION
    assert fast["ha_performance_score"] > slow["ha_performance_score"]
    assert fast["ha_core_score"] > slow["ha_core_score"]
    assert fast["fluidity_score"] > slow["fluidity_score"]


def test_poor_subsystem_is_not_hidden() -> None:
    balanced = measurement_set(1)
    degraded = measurement_set(1)
    degraded["state_machine"]["p95_ms"] = 50
    degraded["state_machine"]["p99_ms"] = 80
    degraded["state_machine"]["max_ms"] = 100
    assert (
        compute_scores(degraded)["ha_core_score"]
        < compute_scores(balanced)["ha_core_score"]
    )


def test_standard_sample_validation() -> None:
    measurements = measurement_set()
    measurements["service_calls"]["count"] = 10
    errors = validate_measurements(
        measurements,
        require_standard_samples=True,
    )
    assert any("unexpected sample count: service_calls" in error for error in errors)


def test_measurement_validation_reports_every_data_shape_error() -> None:
    measurements = measurement_set()
    measurements.pop("event_loop_idle")
    measurements["event_loop_loaded"]["p95_ms"] = "invalid"
    measurements["state_machine"]["stddev_ms"] = -1
    measurements["event_bus"].update(
        {"min_ms": 2, "p50_ms": 1, "mean_ms": 4, "max_ms": 3}
    )
    measurements["service_calls"]["count"] = True

    errors = validate_measurements(measurements, require_standard_samples=True)

    assert "missing section: event_loop_idle" in errors
    assert "invalid value: event_loop_loaded.p95_ms" in errors
    assert "negative value: state_machine.stddev_ms" in errors
    assert "inconsistent percentiles: event_bus" in errors
    assert "inconsistent mean: event_bus" in errors
    assert any("unexpected sample count: service_calls" in error for error in errors)


def test_missing_measurement_fails_score() -> None:
    measurements = measurement_set()
    measurements.pop("event_bus")
    with pytest.raises(ValueError, match="missing section"):
        compute_scores(measurements)

"""Pure scoring and statistics helpers for benchmark protocol v3.

This module deliberately has no Home Assistant imports. The integration and the
GitHub worldlist builder both load this exact implementation so public scores
are recomputed from submitted measurements instead of trusted from the payload.
"""

from __future__ import annotations

import math
import statistics
from collections.abc import Mapping, Sequence
from itertools import pairwise
from typing import Any, Final

SCORE_VERSION: Final = "ha_score_v3"
SCORE_MAX: Final = 10_000
SCORE_FLOOR: Final = 0.02

REQUIRED_MEASUREMENTS: Final = (
    "event_loop_idle",
    "event_loop_loaded",
    "state_machine",
    "event_bus",
    "service_calls",
    "template_render",
)

MIN_STANDARD_SAMPLES: Final = {
    "event_loop_idle": 300,
    "event_loop_loaded": 300,
    "state_machine": 300,
    "event_bus": 300,
    "service_calls": 200,
    "template_render": 300,
}

# Values are (ideal, poor, weight). Lower latency is better. The logarithmic
# scale keeps meaningful differences visible on both fast and slow systems.
CORE_COMPONENTS: Final = {
    "event_loop_loaded": ("p95_ms", 0.50, 50.0, 0.30),
    "state_machine": ("p95_ms", 0.70, 50.0, 0.25),
    "event_bus": ("p95_ms", 0.30, 25.0, 0.15),
    "service_calls": ("p95_ms", 0.50, 40.0, 0.15),
    "template_render": ("p95_ms", 0.50, 20.0, 0.10),
}

FLUIDITY_COMPONENTS: Final = {
    "event_loop_idle_p95": ("event_loop_idle", "p95_ms", 0.25, 20.0, 0.40),
    "event_loop_idle_p99": ("event_loop_idle", "p99_ms", 0.60, 60.0, 0.25),
    "event_loop_loaded_p99": (
        "event_loop_loaded",
        "p99_ms",
        1.25,
        120.0,
        0.20,
    ),
}


def percentile(values: Sequence[float], quantile: float) -> float:
    """Return an interpolated percentile for a non-empty sequence."""
    if not values:
        raise ValueError("percentile requires at least one value")
    ordered = sorted(float(value) for value in values)
    if len(ordered) == 1:
        return ordered[0]
    position = (len(ordered) - 1) * max(0.0, min(1.0, quantile))
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return ordered[lower]
    fraction = position - lower
    return ordered[lower] + (ordered[upper] - ordered[lower]) * fraction


def summarize_samples(
    values: Sequence[float],
    *,
    elapsed_s: float | None = None,
    spike_thresholds_ms: Sequence[int] = (20, 50, 100),
) -> dict[str, int | float]:
    """Summarize latency samples without persisting bulky raw arrays."""
    clean = [
        float(value)
        for value in values
        if isinstance(value, int | float)
        and math.isfinite(float(value))
        and float(value) >= 0
    ]
    if not clean:
        raise ValueError("No valid benchmark samples")

    mean = statistics.fmean(clean)
    stddev = statistics.pstdev(clean) if len(clean) > 1 else 0.0
    summary: dict[str, int | float] = {
        "count": len(clean),
        "min_ms": round(min(clean), 6),
        "mean_ms": round(mean, 6),
        "p50_ms": round(percentile(clean, 0.50), 6),
        "p95_ms": round(percentile(clean, 0.95), 6),
        "p99_ms": round(percentile(clean, 0.99), 6),
        "max_ms": round(max(clean), 6),
        "stddev_ms": round(stddev, 6),
        "cv": round(stddev / mean, 6) if mean > 0 else 0.0,
    }
    for threshold in spike_thresholds_ms:
        count = sum(value > threshold for value in clean)
        summary[f"spikes_over_{threshold}ms"] = count
        summary[f"spike_rate_over_{threshold}ms"] = round(count / len(clean), 6)
    if elapsed_s and elapsed_s > 0:
        summary["throughput_ops_s"] = round(len(clean) / elapsed_s, 3)
    return summary


def normalize_lower(value: Any, ideal: float, poor: float) -> float:
    """Normalize a lower-is-better metric with a logarithmic curve."""
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return 0.0
    if not math.isfinite(parsed) or parsed < 0 or ideal <= 0 or poor <= ideal:
        return 0.0
    if parsed <= ideal:
        return 1.0
    if parsed >= poor:
        return 0.0
    return max(
        0.0,
        min(1.0, math.log(poor / parsed) / math.log(poor / ideal)),
    )


def _measurement_value(
    measurements: Mapping[str, Any], section: str, key: str
) -> float:
    value = measurements.get(section, {}).get(key)
    if not isinstance(value, int | float) or not math.isfinite(float(value)):
        raise ValueError(f"Invalid measurement: {section}.{key}")
    return float(value)


def _weighted_geometric(components: Mapping[str, tuple[float, float]]) -> float:
    total_weight = sum(weight for _, weight in components.values())
    if total_weight <= 0:
        return 0.0
    logarithm = sum(
        weight * math.log(max(SCORE_FLOOR, min(1.0, quality)))
        for quality, weight in components.values()
    )
    return math.exp(logarithm / total_weight)


def _stability_quality(measurements: Mapping[str, Any]) -> tuple[float, float]:
    adjusted_coefficients = []
    for section in REQUIRED_MEASUREMENTS:
        mean = _measurement_value(measurements, section, "mean_ms")
        stddev = _measurement_value(measurements, section, "stddev_ms")
        adjusted_coefficients.append(stddev / max(mean, 0.1))
    average_adjusted_cv = statistics.fmean(adjusted_coefficients)
    return (
        normalize_lower(average_adjusted_cv, 0.12, 1.20),
        average_adjusted_cv,
    )


def validate_measurements(
    measurements: Mapping[str, Any],
    *,
    require_standard_samples: bool = False,
) -> list[str]:
    """Return validation errors for a measurement set."""
    errors: list[str] = []
    for section in REQUIRED_MEASUREMENTS:
        data = measurements.get(section)
        if not isinstance(data, Mapping):
            errors.append(f"missing section: {section}")
            continue
        for key in (
            "count",
            "min_ms",
            "mean_ms",
            "p50_ms",
            "p95_ms",
            "p99_ms",
            "max_ms",
            "stddev_ms",
            "cv",
        ):
            value = data.get(key)
            if not isinstance(value, int | float) or not math.isfinite(float(value)):
                errors.append(f"invalid value: {section}.{key}")
            elif float(value) < 0:
                errors.append(f"negative value: {section}.{key}")
        ordered_values = [
            data.get("min_ms"),
            data.get("p50_ms"),
            data.get("p95_ms"),
            data.get("p99_ms"),
            data.get("max_ms"),
        ]
        if all(isinstance(value, int | float) for value in ordered_values) and any(
            float(left) > float(right) for left, right in pairwise(ordered_values)
        ):
            errors.append(f"inconsistent percentiles: {section}")
        mean = data.get("mean_ms")
        minimum = data.get("min_ms")
        maximum = data.get("max_ms")
        if (
            isinstance(mean, int | float)
            and isinstance(minimum, int | float)
            and isinstance(maximum, int | float)
            and not float(minimum) <= float(mean) <= float(maximum)
        ):
            errors.append(f"inconsistent mean: {section}")
        if require_standard_samples:
            count = data.get("count")
            minimum = MIN_STANDARD_SAMPLES[section]
            if (
                not isinstance(count, int)
                or isinstance(count, bool)
                or count != minimum
            ):
                errors.append(
                    f"unexpected sample count: {section} ({count!r} != {minimum})"
                )
    return errors


def compute_scores(measurements: Mapping[str, Any]) -> dict[str, Any]:
    """Compute the versioned HA-centric benchmark scores."""
    errors = validate_measurements(measurements)
    if errors:
        raise ValueError("; ".join(errors))

    core_components: dict[str, tuple[float, float]] = {}
    normalized: dict[str, float] = {}
    for section, (key, ideal, poor, weight) in CORE_COMPONENTS.items():
        quality = normalize_lower(
            _measurement_value(measurements, section, key),
            ideal,
            poor,
        )
        core_components[section] = (quality, weight)
        normalized[section] = round(quality, 6)

    stability, average_cv = _stability_quality(measurements)
    core_components["stability"] = (stability, 0.05)
    normalized["stability"] = round(stability, 6)

    fluidity_components: dict[str, tuple[float, float]] = {}
    for name, (section, key, ideal, poor, weight) in FLUIDITY_COMPONENTS.items():
        quality = normalize_lower(
            _measurement_value(measurements, section, key),
            ideal,
            poor,
        )
        fluidity_components[name] = (quality, weight)
        normalized[name] = round(quality, 6)

    idle_p95 = _measurement_value(
        measurements,
        "event_loop_idle",
        "p95_ms",
    )
    loaded_p95 = _measurement_value(
        measurements,
        "event_loop_loaded",
        "p95_ms",
    )
    slowdown_ratio = (loaded_p95 + 0.5) / (idle_p95 + 0.5)
    slowdown_quality = normalize_lower(slowdown_ratio, 1.25, 10.0)
    fluidity_components["controlled_load_slowdown"] = (slowdown_quality, 0.15)
    normalized["controlled_load_slowdown"] = round(slowdown_quality, 6)

    core_quality = _weighted_geometric(core_components)
    fluidity_quality = _weighted_geometric(fluidity_components)
    overall_quality = _weighted_geometric(
        {
            "core": (core_quality, 0.70),
            "fluidity": (fluidity_quality, 0.30),
        }
    )

    component_scores = {
        key: round(value * SCORE_MAX) for key, value in normalized.items()
    }
    return {
        "score_version": SCORE_VERSION,
        "ha_performance_score": round(overall_quality * SCORE_MAX),
        "ha_core_score": round(core_quality * SCORE_MAX),
        "fluidity_score": round(fluidity_quality * SCORE_MAX),
        "component_scores": component_scores,
        "normalized": normalized,
        "derived": {
            "average_cv": round(average_cv, 6),
            "controlled_load_slowdown_ratio": round(slowdown_ratio, 6),
        },
        "weights": {
            "overall": {"core": 0.70, "fluidity": 0.30},
            "core": {
                "event_loop_loaded": 0.30,
                "state_machine": 0.25,
                "event_bus": 0.15,
                "service_calls": 0.15,
                "template_render": 0.10,
                "stability": 0.05,
            },
            "fluidity": {
                "event_loop_idle_p95": 0.40,
                "event_loop_idle_p99": 0.25,
                "event_loop_loaded_p99": 0.20,
                "controlled_load_slowdown": 0.15,
            },
        },
    }

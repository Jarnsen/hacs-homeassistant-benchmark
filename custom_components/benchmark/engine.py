"""Home Assistant-centric benchmark engine."""

from __future__ import annotations

import asyncio
import datetime as dt
import os
import platform
import shutil
import uuid
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from homeassistant.const import EVENT_STATE_CHANGED
from homeassistant.const import __version__ as ha_version
from homeassistant.core import Event, HomeAssistant, ServiceCall, callback
from homeassistant.helpers import device_registry
from homeassistant.helpers.template import Template

from .const import (
    INTERNAL_PROBE_DOMAIN,
    INTERNAL_PROBE_EVENT,
    INTERNAL_PROBE_SERVICE,
    PROFILE_ALIASES,
    PROFILE_EXTENDED,
    PROFILE_QUICK,
    PROFILE_STANDARD,
    PROTOCOL_VERSION,
    RESULT_SCHEMA,
)
from .scoring import compute_scores, summarize_samples, validate_measurements

ProgressCallback = Callable[[int, str], Awaitable[None]]


@dataclass(frozen=True, slots=True)
class BenchmarkProfile:
    """A fixed protocol profile."""

    name: str
    idle_loop_samples: int
    state_samples: int
    event_samples: int
    service_samples: int
    template_samples: int
    loaded_loop_samples: int
    timer_interval_s: float = 0.01


PROFILES: dict[str, BenchmarkProfile] = {
    PROFILE_QUICK: BenchmarkProfile(
        PROFILE_QUICK,
        idle_loop_samples=60,
        state_samples=40,
        event_samples=40,
        service_samples=30,
        template_samples=30,
        loaded_loop_samples=60,
    ),
    PROFILE_STANDARD: BenchmarkProfile(
        PROFILE_STANDARD,
        idle_loop_samples=300,
        state_samples=300,
        event_samples=300,
        service_samples=200,
        template_samples=300,
        loaded_loop_samples=300,
        timer_interval_s=0.02,
    ),
    PROFILE_EXTENDED: BenchmarkProfile(
        PROFILE_EXTENDED,
        idle_loop_samples=600,
        state_samples=600,
        event_samples=600,
        service_samples=400,
        template_samples=600,
        loaded_loop_samples=600,
        timer_interval_s=0.02,
    ),
}


def canonical_profile(profile: str | None) -> str:
    """Return a supported v3 profile while accepting v2 aliases."""
    value = (profile or PROFILE_STANDARD).lower()
    value = PROFILE_ALIASES.get(value, value)
    if value not in PROFILES:
        raise ValueError(f"Unsupported benchmark profile: {profile}")
    return value


def _ram_total_mb() -> int | None:
    """Return host RAM using the standard library where supported."""
    try:
        pages = os.sysconf("SC_PHYS_PAGES")
        page_size = os.sysconf("SC_PAGE_SIZE")
    except (AttributeError, OSError, ValueError):
        return None
    if not isinstance(pages, int) or not isinstance(page_size, int):
        return None
    return round((pages * page_size) / 1024 / 1024)


def _collect_host_metadata(config_path: str) -> dict[str, Any]:
    """Collect secondary host metadata outside the event loop."""
    disk = shutil.disk_usage(config_path)
    try:
        load_average = [round(value, 3) for value in os.getloadavg()]
    except (AttributeError, OSError):
        load_average = None
    cpu_model = platform.processor().strip() or None
    if cpu_model is None:
        try:
            cpu_lines = Path("/proc/cpuinfo").read_text(
                encoding="utf-8",
                errors="replace",
            )
        except OSError:
            cpu_lines = ""
        for line in cpu_lines.splitlines():
            key, separator, value = line.partition(":")
            if separator and key.strip().lower() in {"model name", "hardware"}:
                cpu_model = value.strip() or None
                if cpu_model:
                    break
    try:
        device_model = (
            Path("/proc/device-tree/model")
            .read_text(encoding="utf-8", errors="replace")
            .rstrip("\x00")
            .strip()
            or None
        )
    except OSError:
        device_model = None
    return {
        "architecture": platform.machine() or None,
        "cpu_model": cpu_model,
        "device_model": device_model,
        "operating_system": platform.platform(),
        "python_version": platform.python_version(),
        "cpu_cores_logical": os.cpu_count(),
        "ram_total_mb": _ram_total_mb(),
        "disk_total_mb": round(disk.total / 1024 / 1024),
        "disk_free_mb": round(disk.free / 1024 / 1024),
        "load_average": load_average,
    }


async def collect_system_metadata(hass: HomeAssistant) -> dict[str, Any]:
    """Collect non-scoring metadata for comparison and diagnostics."""
    host = await hass.async_add_executor_job(
        _collect_host_metadata,
        hass.config.path(),
    )
    registry = device_registry.async_get(hass)
    return {
        "home_assistant_version": ha_version,
        "installation_type": (
            "home_assistant_os_or_supervised"
            if "hassio" in hass.config.components
            else "container_or_core"
        ),
        "entity_count": len(hass.states.async_all()),
        "device_count": len(registry.devices),
        "config_entry_count": len(hass.config_entries.async_entries()),
        "recorder_loaded": "recorder" in hass.config.components,
        **host,
    }


async def _measure_timer_lag(
    sample_count: int,
    interval_s: float,
) -> list[float]:
    """Measure event-loop scheduling lateness."""
    loop = asyncio.get_running_loop()
    values: list[float] = []
    for _ in range(sample_count):
        target = loop.time() + interval_s
        await asyncio.sleep(interval_s)
        values.append(max(0.0, (loop.time() - target) * 1000))
    return values


async def _measure_state_machine(
    hass: HomeAssistant,
    entity_id: str,
    sample_count: int,
) -> tuple[list[float], float]:
    """Measure state-set to state_changed-listener latency."""
    loop = asyncio.get_running_loop()
    future: asyncio.Future[float] | None = None
    expected_state: str | None = None

    @callback
    def _state_listener(event: Event) -> None:
        nonlocal future
        new_state = event.data.get("new_state")
        if (
            future is not None
            and not future.done()
            and new_state is not None
            and new_state.entity_id == entity_id
            and new_state.state == expected_state
        ):
            future.set_result(loop.time())

    unsubscribe = hass.bus.async_listen(EVENT_STATE_CHANGED, _state_listener)
    values: list[float] = []
    started = loop.time()
    try:
        for index in range(sample_count):
            expected_state = str(index)
            future = loop.create_future()
            sample_start = loop.time()
            hass.states.async_set(
                entity_id,
                expected_state,
                {"benchmark_internal": True},
            )
            completed = await asyncio.wait_for(future, timeout=2)
            values.append((completed - sample_start) * 1000)
    finally:
        unsubscribe()
        hass.states.async_remove(entity_id)
    return values, loop.time() - started


async def _measure_event_bus(
    hass: HomeAssistant,
    probe_id: str,
    sample_count: int,
) -> tuple[list[float], float]:
    """Measure event-fire to listener latency."""
    loop = asyncio.get_running_loop()
    future: asyncio.Future[float] | None = None
    expected_sequence = -1

    @callback
    def _event_listener(event: Event) -> None:
        nonlocal future
        if (
            future is not None
            and not future.done()
            and event.data.get("probe_id") == probe_id
            and event.data.get("sequence") == expected_sequence
        ):
            future.set_result(loop.time())

    unsubscribe = hass.bus.async_listen(INTERNAL_PROBE_EVENT, _event_listener)
    values: list[float] = []
    started = loop.time()
    try:
        for index in range(sample_count):
            expected_sequence = index
            future = loop.create_future()
            sample_start = loop.time()
            hass.bus.async_fire(
                INTERNAL_PROBE_EVENT,
                {"probe_id": probe_id, "sequence": index},
            )
            completed = await asyncio.wait_for(future, timeout=2)
            values.append((completed - sample_start) * 1000)
    finally:
        unsubscribe()
    return values, loop.time() - started


async def _measure_service_calls(
    hass: HomeAssistant,
    service_name: str,
    sample_count: int,
) -> tuple[list[float], float]:
    """Measure the Home Assistant service dispatch pipeline."""
    loop = asyncio.get_running_loop()
    values: list[float] = []
    started = loop.time()
    for index in range(sample_count):
        sample_start = loop.time()
        await hass.services.async_call(
            INTERNAL_PROBE_DOMAIN,
            service_name,
            {"sequence": index},
            blocking=True,
        )
        values.append((loop.time() - sample_start) * 1000)
    return values, loop.time() - started


def _template_suite(hass: HomeAssistant, entity_ids: list[str]) -> list[Template]:
    quoted_ids = ", ".join(f"'{entity_id}'" for entity_id in entity_ids)
    return [
        Template(
            f"{{{{ (states('{entity_ids[0]}') | int) "
            f"+ (states('{entity_ids[1]}') | int) }}}}",
            hass,
        ),
        Template(
            "{% set ns = namespace(total=0) %}"
            "{% for index in range(12) %}"
            "{% set ns.total = ns.total "
            f"+ states('{entity_ids[0][:-1]}' ~ index) | int %}}"
            "{% endfor %}{{ ns.total }}",
            hass,
        ),
        Template(
            "{{ expand([" + quoted_ids + "]) "
            "| map(attribute='state') | map('int') | sum }}",
            hass,
        ),
    ]


async def _measure_template_render(
    hass: HomeAssistant,
    probe_id: str,
    sample_count: int,
) -> tuple[list[float], float]:
    """Measure realistic, warmed Home Assistant template rendering."""
    loop = asyncio.get_running_loop()
    entity_ids = [
        f"{INTERNAL_PROBE_DOMAIN}.value_{probe_id}_{index}" for index in range(12)
    ]
    for index, entity_id in enumerate(entity_ids):
        hass.states.async_set(
            entity_id,
            str(index + 1),
            {"benchmark_internal": True},
        )

    templates = _template_suite(hass, entity_ids)
    values: list[float] = []
    try:
        for template in templates:
            template.async_render(parse_result=False)
        started = loop.time()
        for index in range(sample_count):
            sample_start = loop.time()
            templates[index % len(templates)].async_render(parse_result=False)
            values.append((loop.time() - sample_start) * 1000)
        elapsed = loop.time() - started
    finally:
        for entity_id in entity_ids:
            hass.states.async_remove(entity_id)
    return values, elapsed


async def _measure_loaded_event_loop(
    hass: HomeAssistant,
    service_name: str,
    sample_count: int,
    interval_s: float,
) -> tuple[list[float], int, float]:
    """Measure loop lag under a fixed-rate HA service workload."""
    stop = asyncio.Event()
    operations = 0
    batch_size = 5
    batch_period_s = 0.02

    async def _controlled_load() -> None:
        nonlocal operations
        loop = asyncio.get_running_loop()
        next_batch = loop.time()
        while not stop.is_set():
            for _ in range(batch_size):
                await hass.services.async_call(
                    INTERNAL_PROBE_DOMAIN,
                    service_name,
                    {"controlled_load": True, "sequence": operations},
                    blocking=True,
                )
                operations += 1
            next_batch += batch_period_s
            delay = next_batch - loop.time()
            if delay > 0:
                await asyncio.sleep(delay)
            else:
                await asyncio.sleep(0)

    loop = asyncio.get_running_loop()
    started = loop.time()
    load_task = hass.async_create_task(
        _controlled_load(),
        "benchmark controlled HA workload",
    )
    try:
        values = await _measure_timer_lag(sample_count, interval_s)
    finally:
        stop.set()
        await load_task
    return values, operations, loop.time() - started


def _confidence(
    measurements: dict[str, dict[str, int | float]],
) -> tuple[str, list[str]]:
    """Classify measurement stability without hiding slow systems."""
    warnings: list[str] = []
    adjusted_coefficients = [
        float(values["stddev_ms"]) / max(float(values["mean_ms"]), 0.1)
        for values in measurements.values()
    ]
    worst_adjusted_cv = max(adjusted_coefficients)
    idle_spike_rate = float(
        measurements["event_loop_idle"].get("spike_rate_over_50ms", 0)
    )
    if idle_spike_rate > 0.02:
        warnings.append("background_activity_detected")
    if worst_adjusted_cv <= 0.50 and idle_spike_rate <= 0.02:
        return "high", warnings
    if worst_adjusted_cv <= 1.00 and idle_spike_rate <= 0.10:
        return "medium", warnings
    warnings.append("high_measurement_variability")
    return "low", warnings


async def run_benchmark(
    hass: HomeAssistant,
    profile_name: str,
    restart_recovery_time_s: float | None,
    progress_callback: ProgressCallback,
) -> dict[str, Any]:
    """Run a complete versioned Home Assistant performance benchmark."""
    profile = PROFILES[canonical_profile(profile_name)]
    result_id = uuid.uuid4().hex
    probe_entity = f"{INTERNAL_PROBE_DOMAIN}.state_{result_id[:8]}"
    service_name = f"{INTERNAL_PROBE_SERVICE}_{result_id[:8]}"
    loop = asyncio.get_running_loop()
    benchmark_started = loop.time()

    @callback
    def _internal_probe_service(_call: ServiceCall) -> None:
        return None

    hass.services.async_register(
        INTERNAL_PROBE_DOMAIN,
        service_name,
        _internal_probe_service,
    )

    try:
        await progress_callback(3, "Preparing controlled HA benchmark")
        system = await collect_system_metadata(hass)

        await progress_callback(10, "Measuring idle event-loop responsiveness")
        idle_loop = await _measure_timer_lag(
            profile.idle_loop_samples,
            profile.timer_interval_s,
        )

        await progress_callback(25, "Measuring state-machine latency")
        state_values, state_elapsed = await _measure_state_machine(
            hass,
            probe_entity,
            profile.state_samples,
        )

        await progress_callback(40, "Measuring event-bus latency")
        event_values, event_elapsed = await _measure_event_bus(
            hass,
            result_id,
            profile.event_samples,
        )

        await progress_callback(55, "Measuring service-call latency")
        service_values, service_elapsed = await _measure_service_calls(
            hass,
            service_name,
            profile.service_samples,
        )

        await progress_callback(68, "Measuring template-engine latency")
        template_values, template_elapsed = await _measure_template_render(
            hass,
            result_id[:8],
            profile.template_samples,
        )

        await progress_callback(82, "Measuring responsiveness under HA load")
        (
            loaded_loop,
            controlled_operations,
            loaded_elapsed,
        ) = await _measure_loaded_event_loop(
            hass,
            service_name,
            profile.loaded_loop_samples,
            profile.timer_interval_s,
        )

        measurements = {
            "event_loop_idle": summarize_samples(idle_loop),
            "event_loop_loaded": {
                **summarize_samples(loaded_loop),
                "controlled_service_calls": controlled_operations,
                "controlled_service_calls_s": round(
                    controlled_operations / loaded_elapsed,
                    3,
                )
                if loaded_elapsed > 0
                else 0.0,
            },
            "state_machine": summarize_samples(
                state_values,
                elapsed_s=state_elapsed,
            ),
            "event_bus": summarize_samples(
                event_values,
                elapsed_s=event_elapsed,
            ),
            "service_calls": summarize_samples(
                service_values,
                elapsed_s=service_elapsed,
            ),
            "template_render": summarize_samples(
                template_values,
                elapsed_s=template_elapsed,
            ),
        }

        await progress_callback(94, "Computing versioned HA scores")
        errors = validate_measurements(
            measurements,
            require_standard_samples=profile.name == PROFILE_STANDARD,
        )
        if errors:
            raise ValueError("; ".join(errors))
        scores = compute_scores(measurements)
        confidence, warnings = _confidence(measurements)
        elapsed_s = loop.time() - benchmark_started

        return {
            "schema": RESULT_SCHEMA,
            "result_id": result_id,
            "timestamp": dt.datetime.now(dt.UTC).isoformat(),
            "protocol_version": PROTOCOL_VERSION,
            "score_version": scores["score_version"],
            "protocol": {
                "timer_interval_ms": round(profile.timer_interval_s * 1000),
                "sample_counts": {
                    "event_loop_idle": profile.idle_loop_samples,
                    "event_loop_loaded": profile.loaded_loop_samples,
                    "state_machine": profile.state_samples,
                    "event_bus": profile.event_samples,
                    "service_calls": profile.service_samples,
                    "template_render": profile.template_samples,
                },
                "controlled_load": {
                    "batch_size": 5,
                    "batch_period_ms": 20,
                    "target_service_calls_s": 250,
                    "state_updates": False,
                },
            },
            "profile": profile.name,
            "duration_s": round(elapsed_s, 3),
            "scores": scores,
            "measurements": measurements,
            "system": system,
            "secondary": {
                "restart_recovery_time_s": restart_recovery_time_s,
            },
            "validity": {
                "completed": True,
                "ranking_eligible": profile.name == PROFILE_STANDARD,
                "confidence": confidence,
                "warnings": warnings,
            },
        }
    finally:
        if hass.services.has_service(
            INTERNAL_PROBE_DOMAIN,
            service_name,
        ):
            hass.services.async_remove(
                INTERNAL_PROBE_DOMAIN,
                service_name,
            )
        hass.states.async_remove(probe_entity)

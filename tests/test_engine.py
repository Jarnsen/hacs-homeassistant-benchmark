"""Focused tests for the Home Assistant measurement engine."""

from __future__ import annotations

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from custom_components.benchmark import engine
from custom_components.benchmark.const import (
    INTERNAL_PROBE_DOMAIN,
    PROFILE_QUICK,
    PROFILE_STANDARD,
)

from .helpers import measurement_set


def test_profile_canonicalization() -> None:
    assert engine.canonical_profile(None) == PROFILE_STANDARD
    assert engine.canonical_profile("NORMAL") == PROFILE_STANDARD
    assert engine.canonical_profile("light") == PROFILE_QUICK
    with pytest.raises(ValueError, match="Unsupported benchmark profile"):
        engine.canonical_profile("turbo")


def test_ram_detection_success_and_failures(monkeypatch) -> None:
    monkeypatch.setattr(
        engine.os, "sysconf", lambda name: 1024 if "PAGES" in name else 4096
    )
    assert engine._ram_total_mb() == 4

    monkeypatch.setattr(engine.os, "sysconf", lambda _name: "invalid")
    assert engine._ram_total_mb() is None

    def _raise(_name):
        raise OSError("unsupported")

    monkeypatch.setattr(engine.os, "sysconf", _raise)
    assert engine._ram_total_mb() is None


def test_collect_host_metadata_fallbacks(monkeypatch) -> None:
    monkeypatch.setattr(
        engine.shutil,
        "disk_usage",
        lambda _path: SimpleNamespace(total=10 * 1024 * 1024, free=4 * 1024 * 1024),
    )
    monkeypatch.setattr(
        engine.os, "getloadavg", lambda: (_ for _ in ()).throw(OSError())
    )
    monkeypatch.setattr(engine.platform, "processor", lambda: "")
    monkeypatch.setattr(engine.platform, "machine", lambda: "test-arch")
    monkeypatch.setattr(engine.platform, "platform", lambda: "test-os")
    monkeypatch.setattr(engine.platform, "python_version", lambda: "3.test")
    monkeypatch.setattr(engine.os, "cpu_count", lambda: 8)
    monkeypatch.setattr(engine, "_ram_total_mb", lambda: 2048)

    def _read_text(path, **_kwargs):
        if str(path) == "/proc/cpuinfo":
            return "ignored: value\nmodel name: Synthetic CPU\n"
        if str(path) == "/proc/device-tree/model":
            return "Synthetic device\x00"
        raise AssertionError(path)

    monkeypatch.setattr(engine.Path, "read_text", _read_text)
    metadata = engine._collect_host_metadata("/config")
    assert metadata == {
        "architecture": "test-arch",
        "cpu_model": "Synthetic CPU",
        "device_model": "Synthetic device",
        "operating_system": "test-os",
        "python_version": "3.test",
        "cpu_cores_logical": 8,
        "ram_total_mb": 2048,
        "disk_total_mb": 10,
        "disk_free_mb": 4,
        "load_average": None,
    }


def test_collect_host_metadata_uses_processor_and_handles_missing_model(
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        engine.shutil,
        "disk_usage",
        lambda _path: SimpleNamespace(total=1024, free=512),
    )
    monkeypatch.setattr(engine.os, "getloadavg", lambda: (1.1111, 2.2222, 3.3333))
    monkeypatch.setattr(engine.platform, "processor", lambda: " Direct CPU ")

    def _missing(_path, **_kwargs):
        raise OSError("missing")

    monkeypatch.setattr(engine.Path, "read_text", _missing)
    metadata = engine._collect_host_metadata("/config")
    assert metadata["cpu_model"] == "Direct CPU"
    assert metadata["device_model"] is None
    assert metadata["load_average"] == [1.111, 2.222, 3.333]


@pytest.mark.parametrize("cpuinfo", [OSError("missing"), "vendor: Test\n"])
def test_collect_host_metadata_handles_cpuinfo_without_model(
    monkeypatch, cpuinfo
) -> None:
    monkeypatch.setattr(
        engine.shutil,
        "disk_usage",
        lambda _path: SimpleNamespace(total=1024, free=512),
    )
    monkeypatch.setattr(engine.platform, "processor", lambda: "")

    def _read_text(path, **_kwargs):
        if str(path) == "/proc/cpuinfo" and isinstance(cpuinfo, str):
            return cpuinfo
        raise cpuinfo if isinstance(cpuinfo, OSError) else OSError("missing model")

    monkeypatch.setattr(engine.Path, "read_text", _read_text)
    metadata = engine._collect_host_metadata("/config")
    assert metadata["cpu_model"] is None
    assert metadata["device_model"] is None


def test_collect_host_metadata_skips_empty_cpu_model(monkeypatch) -> None:
    monkeypatch.setattr(
        engine.shutil,
        "disk_usage",
        lambda _path: SimpleNamespace(total=1024, free=512),
    )
    monkeypatch.setattr(engine.platform, "processor", lambda: "")

    def _read_text(path, **_kwargs):
        if str(path) == "/proc/cpuinfo":
            return "model name:   \nmodel name: Fallback CPU\n"
        raise OSError("missing model")

    monkeypatch.setattr(engine.Path, "read_text", _read_text)
    assert engine._collect_host_metadata("/config")["cpu_model"] == "Fallback CPU"


async def test_collect_system_metadata_classifies_installation(
    hass, monkeypatch
) -> None:
    monkeypatch.setattr(
        engine,
        "_collect_host_metadata",
        lambda _path: {"architecture": "test"},
    )
    hass.config.components.add("hassio")
    hass.config.components.add("recorder")
    hass.states.async_set("sensor.example", "1")

    metadata = await engine.collect_system_metadata(hass)

    assert metadata["installation_type"] == "home_assistant_os_or_supervised"
    assert metadata["recorder_loaded"] is True
    assert metadata["entity_count"] >= 1
    assert metadata["architecture"] == "test"


async def test_low_level_measurement_helpers(hass, monkeypatch) -> None:
    timer_values = await engine._measure_timer_lag(1, 0)
    assert len(timer_values) == 1
    assert timer_values[0] >= 0

    state_values, state_elapsed = await engine._measure_state_machine(
        hass, "benchmark_probe.test", 1
    )
    assert len(state_values) == 1
    assert state_elapsed >= 0
    assert hass.states.get("benchmark_probe.test") is None

    event_values, event_elapsed = await engine._measure_event_bus(hass, "probe", 1)
    assert len(event_values) == 1
    assert event_elapsed >= 0

    hass.services.async_register(INTERNAL_PROBE_DOMAIN, "test", lambda _call: None)
    service_values, service_elapsed = await engine._measure_service_calls(
        hass, "test", 1
    )
    assert len(service_values) == 1
    assert service_elapsed >= 0

    template_values, template_elapsed = await engine._measure_template_render(
        hass, "probe", 3
    )
    assert len(template_values) == 3
    assert template_elapsed >= 0
    assert not hass.states.async_entity_ids(INTERNAL_PROBE_DOMAIN)

    async def _short_timer(_sample_count, _interval_s):
        await asyncio.sleep(0)
        return [0.0]

    monkeypatch.setattr(engine, "_measure_timer_lag", _short_timer)
    loaded, operations, elapsed = await engine._measure_loaded_event_loop(
        hass, "test", 1, 0
    )
    assert loaded == [0.0]
    assert operations >= 5
    assert elapsed >= 0


async def test_measurement_listeners_ignore_unrelated_events(hass) -> None:
    async def _state_noise() -> None:
        for index in range(4):
            await asyncio.sleep(0)
            hass.states.async_set("sensor.unrelated", str(index))

    state_task = asyncio.create_task(
        engine._measure_state_machine(hass, "benchmark_probe.target", 3)
    )
    await asyncio.gather(state_task, _state_noise())
    assert len(state_task.result()[0]) == 3

    async def _event_noise() -> None:
        for index in range(4):
            await asyncio.sleep(0)
            hass.bus.async_fire(
                "benchmark_latency_probe",
                {"probe_id": "other", "sequence": index},
            )

    event_task = asyncio.create_task(engine._measure_event_bus(hass, "target", 3))
    await asyncio.gather(event_task, _event_noise())
    assert len(event_task.result()[0]) == 3


async def test_measurement_listeners_ignore_events_before_probe_is_ready() -> None:
    class FakeBus:
        listener = None

        def async_listen(self, _event_type, listener):
            self.listener = listener
            listener(SimpleNamespace(data={}))
            return lambda: None

        def async_fire(self, _event_type, data):
            self.listener(SimpleNamespace(data=data))

    class FakeStates:
        def __init__(self, bus) -> None:
            self.bus = bus

        def async_set(self, entity_id, state, _attributes) -> None:
            new_state = SimpleNamespace(entity_id=entity_id, state=state)
            self.bus.listener(SimpleNamespace(data={"new_state": new_state}))

        def async_remove(self, _entity_id) -> None:
            pass

    state_bus = FakeBus()
    state_hass = SimpleNamespace(bus=state_bus, states=FakeStates(state_bus))
    values, _elapsed = await engine._measure_state_machine(
        state_hass, "benchmark_probe.target", 1
    )
    assert len(values) == 1

    event_bus = FakeBus()
    event_hass = SimpleNamespace(bus=event_bus)
    values, _elapsed = await engine._measure_event_bus(event_hass, "target", 1)
    assert len(values) == 1


async def test_loaded_loop_waits_for_next_controlled_batch(monkeypatch) -> None:
    fake_hass = SimpleNamespace(
        services=SimpleNamespace(async_call=AsyncMock()),
        async_create_task=lambda coroutine, _name: asyncio.create_task(coroutine),
    )

    async def _timer(_sample_count, _interval_s):
        await asyncio.sleep(0.025)
        return [0.0]

    monkeypatch.setattr(engine, "_measure_timer_lag", _timer)
    values, operations, _elapsed = await engine._measure_loaded_event_loop(
        fake_hass, "test", 1, 0
    )
    assert values == [0.0]
    assert operations >= 5


async def test_loaded_loop_yields_when_controlled_batch_is_late(monkeypatch) -> None:
    async def _slow_service_call(*_args, **_kwargs) -> None:
        await asyncio.sleep(0.005)

    fake_hass = SimpleNamespace(
        services=SimpleNamespace(async_call=AsyncMock(side_effect=_slow_service_call)),
        async_create_task=lambda coroutine, _name: asyncio.create_task(coroutine),
    )

    async def _timer(_sample_count, _interval_s):
        await asyncio.sleep(0.03)
        return [0.0]

    monkeypatch.setattr(engine, "_measure_timer_lag", _timer)
    values, operations, _elapsed = await engine._measure_loaded_event_loop(
        fake_hass, "test", 1, 0
    )
    assert values == [0.0]
    assert operations >= 5


def test_confidence_levels_and_warnings() -> None:
    high = measurement_set()
    assert engine._confidence(high) == ("high", [])

    medium = measurement_set()
    medium["event_bus"]["stddev_ms"] = 0.7
    assert engine._confidence(medium) == ("medium", [])

    low = measurement_set()
    low["event_loop_idle"]["stddev_ms"] = 2
    low["event_loop_idle"]["spike_rate_over_50ms"] = 0.2
    confidence, warnings = engine._confidence(low)
    assert confidence == "low"
    assert warnings == [
        "background_activity_detected",
        "high_measurement_variability",
    ]


def _patch_fast_measurements(monkeypatch, *, loaded_elapsed: float = 1.0) -> None:
    async def _timer(count, _interval):
        return [1.0] * count

    async def _state(_hass, _entity, count):
        return [1.0] * count, 1.0

    async def _event(_hass, _probe, count):
        return [1.0] * count, 1.0

    async def _service(_hass, _service, count):
        await _hass.services.async_call(
            INTERNAL_PROBE_DOMAIN,
            _service,
            {},
            blocking=True,
        )
        return [1.0] * count, 1.0

    async def _template(_hass, _probe, count):
        return [1.0] * count, 1.0

    async def _loaded(_hass, _service, count, _interval):
        return [1.0] * count, 10, loaded_elapsed

    monkeypatch.setattr(engine, "collect_system_metadata", AsyncMock(return_value={}))
    monkeypatch.setattr(engine, "_measure_timer_lag", _timer)
    monkeypatch.setattr(engine, "_measure_state_machine", _state)
    monkeypatch.setattr(engine, "_measure_event_bus", _event)
    monkeypatch.setattr(engine, "_measure_service_calls", _service)
    monkeypatch.setattr(engine, "_measure_template_render", _template)
    monkeypatch.setattr(engine, "_measure_loaded_event_loop", _loaded)


async def test_run_benchmark_fast_protocol_and_cleanup(hass, monkeypatch) -> None:
    _patch_fast_measurements(monkeypatch, loaded_elapsed=0)
    progress = AsyncMock()

    result = await engine.run_benchmark(hass, PROFILE_STANDARD, 4.2, progress)

    assert result["profile"] == PROFILE_STANDARD
    assert result["validity"]["ranking_eligible"] is True
    assert result["secondary"]["restart_recovery_time_s"] == 4.2
    assert (
        result["measurements"]["event_loop_loaded"]["controlled_service_calls_s"] == 0
    )
    assert progress.await_count == 8
    assert not hass.services.async_services().get(INTERNAL_PROBE_DOMAIN)


async def test_run_benchmark_validation_failure_still_cleans_up(
    hass, monkeypatch
) -> None:
    _patch_fast_measurements(monkeypatch)
    monkeypatch.setattr(
        engine, "validate_measurements", lambda *_args, **_kwargs: ["bad"]
    )

    with pytest.raises(ValueError, match="bad"):
        await engine.run_benchmark(hass, PROFILE_QUICK, None, AsyncMock())

    assert not hass.services.async_services().get(INTERNAL_PROBE_DOMAIN)


async def test_run_benchmark_handles_service_removed_during_failure(
    hass, monkeypatch
) -> None:
    monkeypatch.setattr(engine, "collect_system_metadata", AsyncMock(return_value={}))

    async def _remove_service_and_fail(_count, _interval):
        service_name = next(iter(hass.services.async_services()[INTERNAL_PROBE_DOMAIN]))
        hass.services.async_remove(INTERNAL_PROBE_DOMAIN, service_name)
        raise RuntimeError("measurement failed")

    monkeypatch.setattr(engine, "_measure_timer_lag", _remove_service_and_fail)
    with pytest.raises(RuntimeError, match="measurement failed"):
        await engine.run_benchmark(hass, PROFILE_QUICK, None, AsyncMock())
    assert not hass.services.async_services().get(INTERNAL_PROBE_DOMAIN)

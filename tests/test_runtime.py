"""Tests for benchmark orchestration and runtime state."""

from __future__ import annotations

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from homeassistant.exceptions import HomeAssistantError
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.benchmark import runtime as runtime_module
from custom_components.benchmark.const import (
    CONF_DEFAULT_PROFILE,
    CONF_NOTIFICATIONS,
    DOMAIN,
    MAX_HISTORY_ENTRIES,
    STATUS_ERROR,
    STATUS_IDLE,
    STATUS_RESTARTING,
)
from custom_components.benchmark.diagnostics import async_get_config_entry_diagnostics
from custom_components.benchmark.runtime import BenchmarkRuntime

from .helpers import benchmark_result, setup_benchmark_entry


def _direct_runtime(hass, stored, *, options=None):
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Benchmark",
        unique_id="direct-runtime",
        version=2,
        options=options or {},
    )
    entry.add_to_hass(hass)
    store = AsyncMock()
    return BenchmarkRuntime(hass, entry, store, stored), store


def test_runtime_initialization_filters_and_limits_history(hass) -> None:
    history = [benchmark_result(score=index) for index in range(110)]
    history.extend([{"schema": "v2"}, "invalid"])
    runtime, _ = _direct_runtime(
        hass,
        {
            "history": history,
            "legacy_history": [1, {"score": 1}],
            "pending_restart": "invalid",
        },
        options={CONF_DEFAULT_PROFILE: "light", CONF_NOTIFICATIONS: False},
    )

    assert len(runtime.history) == MAX_HISTORY_ENTRIES
    assert runtime.latest["scores"]["ha_performance_score"] == 109
    assert runtime.legacy_history == [{"score": 1}]
    assert runtime.pending_restart is None
    assert runtime.default_profile == "quick"
    assert not runtime.notifications_enabled
    snapshot = runtime.snapshot()
    assert snapshot["local_best_score"] == 109
    assert snapshot["history_count"] == MAX_HISTORY_ENTRIES
    assert snapshot["legacy_history_count"] == 1


async def test_progress_clamps_and_save_serializes_state(hass) -> None:
    runtime, store = _direct_runtime(hass, {})
    runtime.history = [benchmark_result()]
    runtime.legacy_history = [{"score": 1}]
    runtime.pending_restart = {"requested_at": 1}

    await runtime._set_progress(150, "Too far")
    assert runtime.progress == 100
    await runtime._set_progress(-5, "Reset")
    assert runtime.progress == 0
    await runtime._save()

    store.async_save.assert_awaited_once()
    saved = store.async_save.await_args.args[0]
    assert saved["history"] == runtime.history
    assert saved["legacy_history"] == runtime.legacy_history
    assert saved["pending_restart"] == runtime.pending_restart


async def test_notifications_respect_setting_and_ignore_failures(
    hass, monkeypatch
) -> None:
    runtime, _ = _direct_runtime(
        hass,
        {},
        options={CONF_NOTIFICATIONS: False},
    )
    call = AsyncMock()
    runtime.hass = SimpleNamespace(services=SimpleNamespace(async_call=call))
    await runtime._notify("Disabled", "message")
    call.assert_not_awaited()

    call.side_effect = RuntimeError("notification backend unavailable")
    await runtime._notify("Forced Notice", "message", force=True)
    call.assert_awaited_once()


async def test_run_success_locking_and_history_limit(hass, monkeypatch) -> None:
    entry = await setup_benchmark_entry(
        hass,
        options={CONF_NOTIFICATIONS: False},
    )
    runtime = entry.runtime_data
    result = benchmark_result(profile="quick")
    monkeypatch.setattr(runtime_module, "run_benchmark", AsyncMock(return_value=result))
    runtime.history = [benchmark_result(score=index) for index in range(100)]

    returned = await runtime.async_run("quick")

    assert returned is result
    assert runtime.latest is result
    assert len(runtime.history) == MAX_HISTORY_ENTRIES
    assert runtime.status == STATUS_IDLE
    assert runtime.progress == 100
    assert not runtime.running

    await runtime._lock.acquire()
    try:
        with pytest.raises(HomeAssistantError, match="already running"):
            await runtime.async_run("quick")
    finally:
        runtime._lock.release()


async def test_cancelled_run_restores_runtime_state(hass, monkeypatch) -> None:
    entry = await setup_benchmark_entry(hass)
    runtime = entry.runtime_data

    async def _cancel(*_args, **_kwargs):
        raise asyncio.CancelledError

    monkeypatch.setattr(runtime_module, "run_benchmark", _cancel)
    with pytest.raises(asyncio.CancelledError):
        await runtime.async_run("quick")

    assert runtime.status == STATUS_ERROR
    assert runtime.last_error == "Benchmark cancelled"
    assert runtime.progress == 0
    assert not runtime.running


async def test_failed_run_is_wrapped_and_notified(hass, monkeypatch) -> None:
    entry = await setup_benchmark_entry(hass)
    runtime = entry.runtime_data
    notify = AsyncMock()
    monkeypatch.setattr(runtime, "_notify", notify)
    monkeypatch.setattr(
        runtime_module,
        "run_benchmark",
        AsyncMock(side_effect=RuntimeError("synthetic failure")),
    )

    with pytest.raises(HomeAssistantError, match="synthetic failure"):
        await runtime.async_run("quick")

    assert runtime.status == STATUS_ERROR
    assert runtime.last_error == "synthetic failure"
    notify.assert_awaited_once_with("Benchmark failed", "synthetic failure", force=True)


async def test_prepare_restart_success_and_failure(hass, monkeypatch) -> None:
    entry = await setup_benchmark_entry(hass)
    runtime = entry.runtime_data
    save = AsyncMock()
    notify = AsyncMock()
    service_call = AsyncMock()
    monkeypatch.setattr(runtime, "_save", save)
    monkeypatch.setattr(runtime, "_notify", notify)
    runtime.hass = SimpleNamespace(services=SimpleNamespace(async_call=service_call))

    await runtime.async_prepare_restart("light")

    assert runtime.pending_restart["profile"] == "quick"
    assert runtime.status == STATUS_RESTARTING
    service_call.assert_awaited_once_with(
        "homeassistant", "restart", {}, blocking=False
    )

    runtime.status = STATUS_IDLE
    service_call.reset_mock()
    service_call.side_effect = RuntimeError("restart denied")
    with pytest.raises(HomeAssistantError, match="Could not restart"):
        await runtime.async_prepare_restart("standard")
    assert runtime.pending_restart is None
    assert runtime.status == STATUS_ERROR
    assert runtime.last_error == "Could not restart Home Assistant: restart denied"


async def test_prepare_restart_rejects_parallel_benchmark(hass) -> None:
    entry = await setup_benchmark_entry(hass)
    runtime = entry.runtime_data
    await runtime._lock.acquire()
    try:
        with pytest.raises(HomeAssistantError, match="already running"):
            await runtime.async_prepare_restart()
    finally:
        runtime._lock.release()


async def test_resume_pending_restart_variants(hass, monkeypatch) -> None:
    entry = await setup_benchmark_entry(hass)
    runtime = entry.runtime_data
    save = AsyncMock()
    run = AsyncMock()
    monkeypatch.setattr(runtime, "_save", save)
    monkeypatch.setattr(runtime, "async_run", run)

    await runtime.async_resume_pending_restart()
    save.assert_not_awaited()

    runtime.pending_restart = {"requested_at": "invalid", "profile": "quick"}
    await runtime.async_resume_pending_restart()
    assert runtime.pending_restart is None
    run.assert_not_awaited()

    runtime.pending_restart = {"requested_at": 990.0, "profile": "normal"}
    monkeypatch.setattr(runtime_module.time, "time", lambda: 1000.0)
    await runtime.async_resume_pending_restart()
    run.assert_awaited_once_with("normal", restart_recovery_time_s=10.0)

    run.reset_mock()
    notify = AsyncMock()
    monkeypatch.setattr(runtime, "_notify", notify)
    runtime.pending_restart = {"requested_at": 0.0, "profile": "quick"}
    await runtime.async_resume_pending_restart()
    assert runtime.status == STATUS_ERROR
    assert runtime.last_error == "Stale restart benchmark request discarded"
    run.assert_not_awaited()
    notify.assert_awaited_once()


def test_worldlist_payload_requires_result_and_removes_private_fields(hass) -> None:
    runtime, _ = _direct_runtime(hass, {})
    with pytest.raises(HomeAssistantError, match="before exporting"):
        runtime.build_worldlist_payload()

    runtime.history = [benchmark_result()]
    payload = runtime.build_worldlist_payload()

    assert payload["result_id"] == "result-1"
    assert payload["system"]["cpu_model"] == "Test CPU"
    assert "disk_free_mb" not in payload["system"]
    assert payload["privacy"]["anonymous"] is True
    assert "hostnames" in payload["privacy"]["excluded"]


async def test_export_methods_update_runtime_state(hass, monkeypatch) -> None:
    entry = await setup_benchmark_entry(hass)
    runtime = entry.runtime_data
    runtime.history = [benchmark_result()]
    monkeypatch.setattr(runtime, "_notify", AsyncMock())

    exported = await runtime.async_export()
    assert exported == runtime.last_export
    assert exported["json"].endswith("benchmark_export.json")
    assert exported["csv"].endswith("benchmark_export.csv")

    worldlist = await runtime.async_export_worldlist()
    assert worldlist.endswith("benchmark_worldlist_export.json")
    assert runtime.last_worldlist_export == worldlist

    runtime.history = [benchmark_result(profile="quick", ranking_eligible=False)]
    with pytest.raises(HomeAssistantError, match="Only the standard profile"):
        await runtime.async_export_worldlist()


async def test_diagnostics_include_latest_result(hass) -> None:
    entry = await setup_benchmark_entry(hass)
    entry.runtime_data.history = [benchmark_result()]
    diagnostics = await async_get_config_entry_diagnostics(hass, entry)
    assert diagnostics["latest"]["schema"] == "ha_homeassistant_performance_result_v3"
    assert diagnostics["latest"]["scores"]["ha_performance_score"] == 8000


async def test_user_guidance_actions_build_expected_notifications(
    hass, monkeypatch
) -> None:
    runtime, _ = _direct_runtime(hass, {})
    runtime.history = [benchmark_result()]
    notify = AsyncMock()
    monkeypatch.setattr(runtime, "_notify", notify)
    monkeypatch.setattr(
        runtime,
        "async_export_worldlist",
        AsyncMock(return_value="/config/worldlist.json"),
    )

    await runtime.async_show_ranking_issue()
    ranking_message = notify.await_args.args[1]
    assert "ranking_submission.yml" in ranking_message
    assert "/config/worldlist.json" in ranking_message

    await runtime.async_show_dashboard()
    assert "```yaml" in notify.await_args.args[1]

    runtime.last_error = "example"
    await runtime.async_show_support_issue()
    assert "prefilled GitHub issue" in notify.await_args.args[1]

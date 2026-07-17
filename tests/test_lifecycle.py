"""Integration lifecycle and service routing tests."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import EVENT_HOMEASSISTANT_STARTED, Platform
from homeassistant.core import CoreState
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components import benchmark
from custom_components.benchmark.const import (
    DOMAIN,
    SERVICE_CREATE_ISSUE,
    SERVICE_CREATE_RANKING_ISSUE,
    SERVICE_EXPORT,
    SERVICE_EXPORT_WORLDLIST,
    SERVICE_RESTART_AND_RUN,
    SERVICE_SETUP_DASHBOARD,
    SERVICE_START,
)
from custom_components.benchmark.runtime import BenchmarkRuntime

from .helpers import setup_benchmark_entry


def test_runtime_lookup_without_loaded_entry_raises(hass) -> None:
    with pytest.raises(ServiceValidationError, match="is not loaded"):
        benchmark._runtime(hass)


async def test_all_registered_services_route_to_runtime(hass, monkeypatch) -> None:
    entry = await setup_benchmark_entry(hass)
    runtime = entry.runtime_data
    methods = {
        "async_run": AsyncMock(),
        "async_prepare_restart": AsyncMock(),
        "async_export": AsyncMock(),
        "async_export_worldlist": AsyncMock(),
        "async_show_ranking_issue": AsyncMock(),
        "async_show_dashboard": AsyncMock(),
        "async_show_support_issue": AsyncMock(),
    }
    for name, mocked in methods.items():
        monkeypatch.setattr(runtime, name, mocked)

    await hass.services.async_call(
        DOMAIN, SERVICE_START, {"profile": "quick"}, blocking=True
    )
    methods["async_run"].assert_awaited_once_with("quick")

    await hass.services.async_call(
        DOMAIN,
        SERVICE_START,
        {"profile": "normal", "restart": True},
        blocking=True,
    )
    await hass.services.async_call(
        DOMAIN, SERVICE_RESTART_AND_RUN, {"profile": "extended"}, blocking=True
    )
    assert methods["async_prepare_restart"].await_args_list[0].args == ("normal",)
    assert methods["async_prepare_restart"].await_args_list[1].args == ("extended",)

    for service, method in (
        (SERVICE_EXPORT, "async_export"),
        (SERVICE_EXPORT_WORLDLIST, "async_export_worldlist"),
        (SERVICE_CREATE_RANKING_ISSUE, "async_show_ranking_issue"),
        (SERVICE_SETUP_DASHBOARD, "async_show_dashboard"),
        (SERVICE_CREATE_ISSUE, "async_show_support_issue"),
    ):
        await hass.services.async_call(DOMAIN, service, blocking=True)
        methods[method].assert_awaited_once_with()


async def test_removed_v2_entities_are_cleaned(hass) -> None:
    entry = MockConfigEntry(domain=DOMAIN, title="Benchmark", unique_id="cleanup")
    entry.add_to_hass(hass)
    registry = er.async_get(hass)
    unique_id = f"{entry.entry_id}_cpu_performance"
    old = registry.async_get_or_create(
        Platform.SENSOR,
        DOMAIN,
        unique_id,
        config_entry=entry,
        suggested_object_id="old_benchmark_cpu",
    )
    assert registry.async_get(old.entity_id) is not None

    benchmark._cleanup_removed_v2_entities(hass, entry)

    assert registry.async_get(old.entity_id) is None


async def test_options_update_requests_reload(hass, monkeypatch) -> None:
    entry = MockConfigEntry(domain=DOMAIN, title="Benchmark", unique_id="options")
    reload_entry = AsyncMock(return_value=True)
    monkeypatch.setattr(hass.config_entries, "async_reload", reload_entry)
    await benchmark._async_options_updated(hass, entry)
    reload_entry.assert_awaited_once_with(entry.entry_id)


async def test_entry_migration_updates_only_v1(hass) -> None:
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Benchmark",
        unique_id="migration",
        version=1,
    )
    entry.add_to_hass(hass)
    assert await benchmark.async_migrate_entry(hass, entry)
    assert entry.version == 2
    assert await benchmark.async_migrate_entry(hass, entry)
    assert entry.version == 2


async def test_pending_restart_resumes_immediately_when_ha_running(
    hass, monkeypatch
) -> None:
    store = AsyncMock()
    monkeypatch.setattr(
        benchmark,
        "async_load_store",
        AsyncMock(
            return_value=(
                store,
                {
                    "history": [],
                    "legacy_history": [],
                    "pending_restart": {"requested_at": 1, "profile": "quick"},
                },
            )
        ),
    )
    resume = AsyncMock()
    monkeypatch.setattr(BenchmarkRuntime, "async_resume_pending_restart", resume)
    entry = MockConfigEntry(domain=DOMAIN, title="Benchmark", unique_id="pending-now")
    entry.add_to_hass(hass)

    assert hass.state is CoreState.running
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    resume.assert_awaited_once()
    assert entry.state is ConfigEntryState.LOADED


async def test_pending_restart_waits_for_started_event(hass, monkeypatch) -> None:
    store = AsyncMock()
    monkeypatch.setattr(
        benchmark,
        "async_load_store",
        AsyncMock(
            return_value=(
                store,
                {
                    "history": [],
                    "legacy_history": [],
                    "pending_restart": {"requested_at": 1, "profile": "quick"},
                },
            )
        ),
    )
    resume = AsyncMock()
    monkeypatch.setattr(BenchmarkRuntime, "async_resume_pending_restart", resume)
    monkeypatch.setattr(
        hass.config_entries,
        "async_forward_entry_setups",
        AsyncMock(),
    )
    entry = MockConfigEntry(domain=DOMAIN, title="Benchmark", unique_id="pending-event")
    entry.add_to_hass(hass)
    original_state = hass.state
    hass.state = CoreState.starting
    try:
        assert await benchmark.async_setup_entry(hass, entry)
        resume.assert_not_awaited()
        hass.bus.async_fire(EVENT_HOMEASSISTANT_STARTED)
        await hass.async_block_till_done()
        resume.assert_awaited_once()
    finally:
        hass.state = original_state

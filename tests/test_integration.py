"""Runtime smoke tests against Home Assistant."""

from __future__ import annotations

import json
import time
from pathlib import Path

import pytest
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.exceptions import HomeAssistantError
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.benchmark.const import (
    DOMAIN,
    EXPORT_CSV_FILE,
    EXPORT_JSON_FILE,
    INTERNAL_PROBE_DOMAIN,
    LEGACY_HISTORY_FILE,
    PROFILE_STANDARD,
    SERVICE_SETUP_DASHBOARD,
    SERVICE_START,
    STATUS_ERROR,
    WORLDLIST_EXPORT_FILE,
)
from custom_components.benchmark.diagnostics import (
    async_get_config_entry_diagnostics,
)


def _read_json_file(path: str) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _write_legacy_history(path: str) -> None:
    Path(path).write_text(
        json.dumps([{"score": 1234, "profile": "normal"}]),
        encoding="utf-8",
    )


def _path_exists(path: str) -> bool:
    return Path(path).exists()


async def setup_entry(hass) -> MockConfigEntry:
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Home Assistant Performance Benchmark",
        unique_id=DOMAIN,
        version=2,
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry


async def test_setup_and_unload(hass) -> None:
    entry = await setup_entry(hass)
    assert hass.services.has_service(DOMAIN, SERVICE_START)
    assert entry.runtime_data.latest is None
    assert hass.states.get("sensor.benchmark_score") is not None
    assert hass.states.get("button.benchmark_start_standard") is not None
    assert await hass.config_entries.async_unload(entry.entry_id)


async def test_quick_benchmark_smoke(hass) -> None:
    entry = await setup_entry(hass)
    result = await entry.runtime_data.async_run("quick")

    assert result["schema"] == "ha_homeassistant_performance_result_v3"
    assert result["profile"] == "quick"
    assert result["protocol"]["timer_interval_ms"] == 10
    assert 0 <= result["scores"]["ha_performance_score"] <= 10_000
    assert result["validity"]["ranking_eligible"] is False
    assert entry.runtime_data.latest == result
    await hass.async_block_till_done()
    score_state = hass.states.get("sensor.benchmark_score")
    assert score_state is not None
    assert int(score_state.state) == result["scores"]["ha_performance_score"]
    assert not hass.services.async_services().get(INTERNAL_PROBE_DOMAIN)
    assert not hass.states.async_entity_ids(INTERNAL_PROBE_DOMAIN)


async def test_legacy_profile_alias(hass) -> None:
    entry = await setup_entry(hass)
    await hass.services.async_call(
        DOMAIN,
        SERVICE_START,
        {"profile": "light"},
        blocking=True,
    )
    assert entry.runtime_data.latest["profile"] == "quick"


async def test_export_history_and_worldlist(hass) -> None:
    entry = await setup_entry(hass)
    runtime = entry.runtime_data
    result = await runtime.async_run(PROFILE_STANDARD)

    paths = await runtime.async_export()
    assert Path(paths["json"]).name == EXPORT_JSON_FILE
    assert Path(paths["csv"]).name == EXPORT_CSV_FILE
    exported = await hass.async_add_executor_job(
        _read_json_file,
        paths["json"],
    )
    assert exported["history"][-1]["result_id"] == result["result_id"]

    worldlist_path = await runtime.async_export_worldlist()
    payload = await hass.async_add_executor_job(
        _read_json_file,
        worldlist_path,
    )
    assert Path(worldlist_path).name == WORLDLIST_EXPORT_FILE
    assert payload["result_id"] == result["result_id"]
    assert "disk_free_mb" not in payload["system"]


async def test_stale_restart_request_is_discarded(hass) -> None:
    entry = await setup_entry(hass)
    runtime = entry.runtime_data
    runtime.pending_restart = {
        "requested_at": time.time() - 3600,
        "profile": "quick",
    }

    await runtime.async_resume_pending_restart()

    assert runtime.pending_restart is None
    assert runtime.status == STATUS_ERROR
    assert runtime.last_error == "Stale restart benchmark request discarded"


async def test_legacy_history_migrates_to_home_assistant_storage(hass) -> None:
    legacy_path = hass.config.path(LEGACY_HISTORY_FILE)
    await hass.async_add_executor_job(
        _write_legacy_history,
        legacy_path,
    )

    entry = await setup_entry(hass)

    assert entry.runtime_data.legacy_history == [{"score": 1234, "profile": "normal"}]
    assert not await hass.async_add_executor_job(_path_exists, legacy_path)


async def test_worldlist_export_requires_standard_profile(hass) -> None:
    entry = await setup_entry(hass)
    await entry.runtime_data.async_run("quick")

    with pytest.raises(HomeAssistantError, match="Only the standard profile"):
        await entry.runtime_data.async_export_worldlist()


async def test_benchmark_failure_is_reported(hass, monkeypatch) -> None:
    entry = await setup_entry(hass)

    async def _fail_benchmark(*_args, **_kwargs):
        raise RuntimeError("synthetic failure")

    monkeypatch.setattr(
        "custom_components.benchmark.runtime.run_benchmark",
        _fail_benchmark,
    )

    with pytest.raises(HomeAssistantError, match="synthetic failure"):
        await entry.runtime_data.async_run("quick")

    assert entry.runtime_data.status == STATUS_ERROR
    assert entry.runtime_data.last_error == "synthetic failure"


async def test_options_diagnostics_and_dashboard_action(hass) -> None:
    entry = await setup_entry(hass)

    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["type"] is FlowResultType.FORM
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {
            "default_profile": "quick",
            "notifications": False,
        },
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    await hass.async_block_till_done()
    assert entry.options["default_profile"] == "quick"

    diagnostics = await async_get_config_entry_diagnostics(hass, entry)
    assert diagnostics["integration_version"] == "3.0.0"
    assert diagnostics["runtime"]["history_count"] == 0

    await hass.services.async_call(
        DOMAIN,
        SERVICE_SETUP_DASHBOARD,
        blocking=True,
    )

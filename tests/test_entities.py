"""Entity behavior tests for benchmark sensors and buttons."""

from __future__ import annotations

import datetime as dt
from unittest.mock import AsyncMock

import pytest

from custom_components.benchmark import button as button_platform
from custom_components.benchmark import sensor as sensor_platform
from custom_components.benchmark.button import (
    ACTION_DASHBOARD,
    ACTION_EXPORT,
    ACTION_ISSUE,
    ACTION_RANKING,
    ACTION_RESTART,
    ACTION_RUN,
    ACTION_WORLDLIST,
    BUTTONS,
    BenchmarkButton,
    BenchmarkButtonDescription,
)
from custom_components.benchmark.const import (
    INTEGRATION_VERSION,
    STATUS_IDLE,
    STATUS_RESTARTING,
)
from custom_components.benchmark.sensor import (
    SENSORS,
    BenchmarkSensor,
    _load_class,
    _path_value,
)

from .helpers import benchmark_result, setup_benchmark_entry


def _description(items, key):
    return next(item for item in items if item.key == key)


def test_sensor_value_helpers_cover_nested_and_load_classes() -> None:
    assert _path_value({"a": {"b": 3}}, ("a", "b")) == 3
    assert _path_value({"a": None}, ("a", "b")) is None
    assert _path_value({}, ()) == {}
    assert _load_class(None) == "unknown"
    assert _load_class(249) == "small"
    assert _load_class(250) == "medium"
    assert _load_class(750) == "large"
    assert _load_class(1500) == "very_large"


async def test_platform_setup_callbacks_add_every_entity(hass) -> None:
    entry = await setup_benchmark_entry(hass)
    sensors = []
    buttons = []
    await sensor_platform.async_setup_entry(hass, entry, sensors.extend)
    await button_platform.async_setup_entry(hass, entry, buttons.extend)
    assert len(sensors) == len(SENSORS)
    assert len(buttons) == len(BUTTONS)


async def test_sensor_native_values_and_attributes(hass) -> None:
    entry = await setup_benchmark_entry(hass)
    runtime = entry.runtime_data
    result = benchmark_result()
    runtime.history = [result]
    runtime.progress_message = "Half way"
    runtime.publish()

    score = BenchmarkSensor(runtime, _description(SENSORS, "score"))
    progress = BenchmarkSensor(runtime, _description(SENSORS, "progress"))
    version = BenchmarkSensor(runtime, _description(SENSORS, "version"))
    last_run = BenchmarkSensor(runtime, _description(SENSORS, "last_run"))
    load_class = BenchmarkSensor(runtime, _description(SENSORS, "load_class"))
    architecture = BenchmarkSensor(runtime, _description(SENSORS, "architecture"))

    assert score.suggested_object_id == "benchmark_score"
    assert score.native_value == 8000
    assert score.extra_state_attributes == {
        "score_version": "ha_score_v3",
        "profile": "standard",
        "confidence": "high",
        "ranking_eligible": True,
        "warnings": [],
    }
    assert progress.extra_state_attributes == {"message": "Half way"}
    assert version.native_value == INTEGRATION_VERSION
    assert last_run.native_value == dt.datetime(2026, 1, 2, 3, 4, tzinfo=dt.UTC)
    assert load_class.native_value == "medium"
    assert architecture.native_value == "x86_64"
    assert architecture.extra_state_attributes is None


async def test_sensor_timestamp_and_numeric_edge_values(hass) -> None:
    entry = await setup_benchmark_entry(hass)
    runtime = entry.runtime_data
    last_run = BenchmarkSensor(runtime, _description(SENSORS, "last_run"))
    restart = BenchmarkSensor(runtime, _description(SENSORS, "restart_time"))

    timestamp = dt.datetime(2026, 1, 1, tzinfo=dt.UTC)
    runtime.coordinator.async_set_updated_data(
        {"latest": {"timestamp": timestamp}, "secondary": {}}
    )
    assert last_run.native_value is timestamp
    runtime.coordinator.async_set_updated_data(
        {"latest": {"timestamp": 123}, "secondary": {}}
    )
    assert last_run.native_value is None
    runtime.coordinator.async_set_updated_data(
        {"latest": {}, "secondary": {"restart_recovery_time_s": 1.236}}
    )
    assert restart.native_value == 1.24


@pytest.mark.parametrize(
    ("action", "method"),
    [
        (ACTION_RUN, "async_run"),
        (ACTION_RESTART, "async_prepare_restart"),
        (ACTION_EXPORT, "async_export"),
        (ACTION_WORLDLIST, "async_export_worldlist"),
        (ACTION_RANKING, "async_show_ranking_issue"),
        (ACTION_DASHBOARD, "async_show_dashboard"),
        (ACTION_ISSUE, "async_show_support_issue"),
    ],
)
async def test_every_button_dispatches_to_runtime(
    hass, monkeypatch, action, method
) -> None:
    entry = await setup_benchmark_entry(hass)
    runtime = entry.runtime_data
    description = next(item for item in BUTTONS if item.action == action)
    mocked = AsyncMock()
    monkeypatch.setattr(runtime, method, mocked)
    entity = BenchmarkButton(runtime, description)

    assert entity.suggested_object_id == description.suggested_object_id
    await entity.async_press()

    if action in (ACTION_RUN, ACTION_RESTART):
        mocked.assert_awaited_once_with(description.profile)
    else:
        mocked.assert_awaited_once_with()


async def test_button_availability_tracks_runtime_state(hass) -> None:
    entry = await setup_benchmark_entry(hass)
    runtime = entry.runtime_data
    run = BenchmarkButton(
        runtime, next(item for item in BUTTONS if item.action == ACTION_RUN)
    )
    restart = BenchmarkButton(
        runtime, next(item for item in BUTTONS if item.action == ACTION_RESTART)
    )
    export = BenchmarkButton(
        runtime, next(item for item in BUTTONS if item.action == ACTION_EXPORT)
    )
    worldlist = BenchmarkButton(
        runtime, next(item for item in BUTTONS if item.action == ACTION_WORLDLIST)
    )
    dashboard = BenchmarkButton(
        runtime, next(item for item in BUTTONS if item.action == ACTION_DASHBOARD)
    )

    assert run.available
    assert restart.available
    assert not export.available
    assert not worldlist.available
    assert dashboard.available

    runtime.running = True
    assert not run.available
    runtime.running = False
    runtime.status = STATUS_RESTARTING
    assert not restart.available
    runtime.status = STATUS_IDLE

    runtime.legacy_history = [{"score": 1}]
    assert export.available
    runtime.legacy_history = []
    runtime.history = [benchmark_result(profile="quick", ranking_eligible=False)]
    assert not worldlist.available
    runtime.history = [benchmark_result(ranking_eligible=False)]
    assert not worldlist.available
    runtime.history = [benchmark_result()]
    assert worldlist.available

    runtime.coordinator.last_update_success = False
    assert not dashboard.available


async def test_unknown_button_action_is_safe_noop(hass) -> None:
    entry = await setup_benchmark_entry(hass)
    entity = BenchmarkButton(
        entry.runtime_data,
        BenchmarkButtonDescription(
            key="future_action",
            action="future",
            suggested_object_id="benchmark_future_action",
        ),
    )
    await entity.async_press()

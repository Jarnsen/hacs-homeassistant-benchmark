"""Sensor entities for Home Assistant Performance Benchmark."""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import PERCENTAGE, UnitOfInformation, UnitOfTime
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import dt as dt_util

from .const import (
    ATTRIBUTION,
    CONFIDENCE_HIGH,
    CONFIDENCE_LOW,
    CONFIDENCE_MEDIUM,
    CONFIDENCE_UNKNOWN,
    INTEGRATION_VERSION,
    PROFILE_EXTENDED,
    PROFILE_QUICK,
    PROFILE_STANDARD,
    STATUS_ERROR,
    STATUS_IDLE,
    STATUS_RESTARTING,
    STATUS_RUNNING,
)
from .runtime import BenchmarkConfigEntry, BenchmarkRuntime


@dataclass(frozen=True, kw_only=True)
class BenchmarkSensorDescription(SensorEntityDescription):
    """Describe a benchmark sensor."""

    path: tuple[str, ...] = ()
    digits: int | None = None
    fixed_value: Any = None
    enum_options: tuple[str, ...] | None = None


SENSORS: tuple[BenchmarkSensorDescription, ...] = (
    BenchmarkSensorDescription(
        key="score",
        translation_key="score",
        icon="mdi:speedometer",
        path=("scores", "ha_performance_score"),
        digits=0,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    BenchmarkSensorDescription(
        key="core_score",
        translation_key="core_score",
        icon="mdi:home-assistant",
        path=("scores", "ha_core_score"),
        digits=0,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    BenchmarkSensorDescription(
        key="fluidity_score",
        translation_key="fluidity_score",
        icon="mdi:waveform",
        path=("scores", "fluidity_score"),
        digits=0,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    BenchmarkSensorDescription(
        key="status",
        translation_key="status",
        icon="mdi:state-machine",
        path=("status",),
        device_class=SensorDeviceClass.ENUM,
        enum_options=(
            STATUS_IDLE,
            STATUS_RUNNING,
            STATUS_RESTARTING,
            STATUS_ERROR,
        ),
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    BenchmarkSensorDescription(
        key="progress",
        translation_key="progress",
        icon="mdi:progress-clock",
        path=("progress",),
        native_unit_of_measurement=PERCENTAGE,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    BenchmarkSensorDescription(
        key="confidence",
        translation_key="confidence",
        icon="mdi:check-decagram-outline",
        path=("confidence",),
        device_class=SensorDeviceClass.ENUM,
        enum_options=(
            CONFIDENCE_HIGH,
            CONFIDENCE_MEDIUM,
            CONFIDENCE_LOW,
            CONFIDENCE_UNKNOWN,
        ),
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    BenchmarkSensorDescription(
        key="active_profile",
        translation_key="active_profile",
        icon="mdi:tune",
        path=("latest", "profile"),
        device_class=SensorDeviceClass.ENUM,
        enum_options=(
            PROFILE_QUICK,
            PROFILE_STANDARD,
            PROFILE_EXTENDED,
        ),
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    BenchmarkSensorDescription(
        key="last_run",
        translation_key="last_run",
        icon="mdi:calendar-clock",
        path=("latest", "timestamp"),
        device_class=SensorDeviceClass.TIMESTAMP,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    BenchmarkSensorDescription(
        key="event_loop_idle",
        translation_key="event_loop_idle",
        icon="mdi:timer-sand",
        path=("measurements", "event_loop_idle", "p95_ms"),
        native_unit_of_measurement=UnitOfTime.MILLISECONDS,
        device_class=SensorDeviceClass.DURATION,
        state_class=SensorStateClass.MEASUREMENT,
        digits=3,
    ),
    BenchmarkSensorDescription(
        key="event_loop_loaded",
        translation_key="event_loop_loaded",
        icon="mdi:timer-alert-outline",
        path=("measurements", "event_loop_loaded", "p95_ms"),
        native_unit_of_measurement=UnitOfTime.MILLISECONDS,
        device_class=SensorDeviceClass.DURATION,
        state_class=SensorStateClass.MEASUREMENT,
        digits=3,
    ),
    BenchmarkSensorDescription(
        key="state_machine",
        translation_key="state_machine",
        icon="mdi:swap-horizontal",
        path=("measurements", "state_machine", "p95_ms"),
        native_unit_of_measurement=UnitOfTime.MILLISECONDS,
        device_class=SensorDeviceClass.DURATION,
        state_class=SensorStateClass.MEASUREMENT,
        digits=3,
    ),
    BenchmarkSensorDescription(
        key="event_bus",
        translation_key="event_bus",
        icon="mdi:message-flash-outline",
        path=("measurements", "event_bus", "p95_ms"),
        native_unit_of_measurement=UnitOfTime.MILLISECONDS,
        device_class=SensorDeviceClass.DURATION,
        state_class=SensorStateClass.MEASUREMENT,
        digits=3,
    ),
    BenchmarkSensorDescription(
        key="service_calls",
        translation_key="service_calls",
        icon="mdi:call-merge",
        path=("measurements", "service_calls", "p95_ms"),
        native_unit_of_measurement=UnitOfTime.MILLISECONDS,
        device_class=SensorDeviceClass.DURATION,
        state_class=SensorStateClass.MEASUREMENT,
        digits=3,
    ),
    BenchmarkSensorDescription(
        key="template_render",
        translation_key="template_render",
        icon="mdi:code-tags",
        path=("measurements", "template_render", "p95_ms"),
        native_unit_of_measurement=UnitOfTime.MILLISECONDS,
        device_class=SensorDeviceClass.DURATION,
        state_class=SensorStateClass.MEASUREMENT,
        digits=3,
    ),
    BenchmarkSensorDescription(
        key="restart_time",
        translation_key="restart_time",
        icon="mdi:restart",
        path=("secondary", "restart_recovery_time_s"),
        native_unit_of_measurement=UnitOfTime.SECONDS,
        device_class=SensorDeviceClass.DURATION,
        state_class=SensorStateClass.MEASUREMENT,
        digits=2,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    BenchmarkSensorDescription(
        key="local_ranking",
        translation_key="local_best_score",
        icon="mdi:trophy-outline",
        path=("local_best_score",),
        digits=0,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    BenchmarkSensorDescription(
        key="history_count",
        translation_key="history_count",
        icon="mdi:history",
        path=("history_count",),
        digits=0,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    BenchmarkSensorDescription(
        key="last_error",
        translation_key="last_error",
        icon="mdi:alert-circle-outline",
        path=("last_error",),
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    BenchmarkSensorDescription(
        key="version",
        translation_key="version",
        icon="mdi:tag-outline",
        fixed_value=INTEGRATION_VERSION,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    BenchmarkSensorDescription(
        key="entity_count",
        translation_key="entity_count",
        icon="mdi:counter",
        path=("system", "entity_count"),
        digits=0,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    BenchmarkSensorDescription(
        key="load_class",
        translation_key="load_class",
        icon="mdi:gauge",
        path=("system", "entity_count"),
        device_class=SensorDeviceClass.ENUM,
        enum_options=("small", "medium", "large", "very_large", "unknown"),
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    BenchmarkSensorDescription(
        key="architecture",
        translation_key="architecture",
        icon="mdi:chip",
        path=("system", "architecture"),
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    BenchmarkSensorDescription(
        key="cpu_model",
        translation_key="cpu_model",
        icon="mdi:chip",
        path=("system", "cpu_model"),
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    BenchmarkSensorDescription(
        key="cpu_cores",
        translation_key="cpu_cores",
        icon="mdi:cpu-64-bit",
        path=("system", "cpu_cores_logical"),
        digits=0,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    BenchmarkSensorDescription(
        key="ram_total",
        translation_key="ram_total",
        icon="mdi:memory",
        path=("system", "ram_total_mb"),
        native_unit_of_measurement=UnitOfInformation.MEGABYTES,
        digits=0,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
)


async def async_setup_entry(
    _hass,
    entry: BenchmarkConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up benchmark sensors."""
    runtime = entry.runtime_data
    async_add_entities(BenchmarkSensor(runtime, description) for description in SENSORS)


def _path_value(data: dict[str, Any], path: tuple[str, ...]) -> Any:
    value: Any = data
    for key in path:
        if not isinstance(value, dict):
            return None
        value = value.get(key)
    return value


def _load_class(entity_count: Any) -> str:
    if not isinstance(entity_count, int | float):
        return "unknown"
    if entity_count < 250:
        return "small"
    if entity_count < 750:
        return "medium"
    if entity_count < 1500:
        return "large"
    return "very_large"


class BenchmarkSensor(CoordinatorEntity, SensorEntity):
    """A coordinator-backed benchmark sensor."""

    entity_description: BenchmarkSensorDescription
    _attr_has_entity_name = True
    _attr_attribution = ATTRIBUTION

    def __init__(
        self,
        runtime: BenchmarkRuntime,
        description: BenchmarkSensorDescription,
    ) -> None:
        super().__init__(runtime.coordinator)
        self.runtime = runtime
        self.entity_description = description
        self._attr_unique_id = f"{runtime.entry.entry_id}_{description.key}"
        self._attr_suggested_object_id = f"benchmark_{description.key}"
        self.internal_integration_suggested_object_id = f"benchmark_{description.key}"
        self.entity_id = f"sensor.benchmark_{description.key}"
        self._attr_device_info = runtime.device_info
        if description.enum_options is not None:
            self._attr_options = list(description.enum_options)

    @property
    def suggested_object_id(self) -> str:
        """Keep documented default entity IDs stable across HA versions."""
        return f"benchmark_{self.entity_description.key}"

    @property
    def native_value(self) -> Any:
        """Return an in-memory benchmark value."""
        description = self.entity_description
        if description.fixed_value is not None:
            value = description.fixed_value
        else:
            value = _path_value(self.coordinator.data, description.path)

        if description.key == "load_class":
            return _load_class(value)
        if description.device_class is SensorDeviceClass.TIMESTAMP:
            if isinstance(value, dt.datetime):
                return value
            if isinstance(value, str):
                return dt_util.parse_datetime(value)
            return None
        if isinstance(value, int | float) and description.digits is not None:
            return round(value, description.digits)
        return value

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Expose only small, recorder-safe explanatory attributes."""
        data = self.coordinator.data
        if self.entity_description.key == "progress":
            return {"message": data.get("progress_message")}
        if self.entity_description.key == "score":
            latest = data.get("latest") or {}
            return {
                "score_version": latest.get("score_version"),
                "profile": latest.get("profile"),
                "confidence": data.get("confidence"),
                "ranking_eligible": data.get("validity", {}).get("ranking_eligible"),
                "warnings": data.get("validity", {}).get("warnings", []),
            }
        return None

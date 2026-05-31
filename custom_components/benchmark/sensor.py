from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from homeassistant.components.sensor import SensorEntity, SensorEntityDescription
from homeassistant.const import PERCENTAGE, UnitOfDataRate, UnitOfTime
from homeassistant.helpers.entity import EntityCategory

from .const import (
    ATTRIBUTION,
    DATA_DASHBOARD_YAML,
    DATA_ENTITIES,
    DATA_LAST_ERROR,
    DATA_LAST_EXPORT,
    DATA_LATEST,
    DATA_PROGRESS,
    DATA_PROGRESS_MESSAGE,
    DATA_RUNNING,
    DOMAIN,
    INTEGRATION_VERSION,
)


@dataclass(frozen=True, kw_only=True)
class BenchmarkSensorDescription(SensorEntityDescription):
    section: str | None = None
    value_key: str | None = None
    value_type: str = "result"
    digits: int | None = None


SENSORS: tuple[BenchmarkSensorDescription, ...] = (
    BenchmarkSensorDescription(key="score", translation_key="score", name="Score", icon="mdi:star", section="results", value_key="benchmark_score", digits=0),
    BenchmarkSensorDescription(key="progress", translation_key="progress", name="Progress", icon="mdi:progress-clock", native_unit_of_measurement=PERCENTAGE, value_type="progress", entity_category=EntityCategory.DIAGNOSTIC),
    BenchmarkSensorDescription(key="status", translation_key="status", name="Status", icon="mdi:state-machine", value_type="status", entity_category=EntityCategory.DIAGNOSTIC),
    BenchmarkSensorDescription(key="active_profile", translation_key="active_profile", name="Active Profile", icon="mdi:tune", value_type="profile", entity_category=EntityCategory.DIAGNOSTIC),
    BenchmarkSensorDescription(key="last_run", translation_key="last_run", name="Last Run", icon="mdi:calendar-clock", value_type="timestamp", entity_category=EntityCategory.DIAGNOSTIC),
    BenchmarkSensorDescription(key="last_error", translation_key="last_error", name="Last Error", icon="mdi:alert-circle-outline", value_type="last_error", entity_category=EntityCategory.DIAGNOSTIC),
    BenchmarkSensorDescription(key="version", translation_key="version", name="Version", icon="mdi:tag-outline", value_type="version", entity_category=EntityCategory.DIAGNOSTIC),
    BenchmarkSensorDescription(key="cpu_performance", translation_key="cpu_performance", name="CPU Performance", icon="mdi:cpu-64-bit", native_unit_of_measurement="ops/s", section="results", value_key="cpu_ops_s", digits=0),
    BenchmarkSensorDescription(key="disk_write", translation_key="disk_write", name="Disk Write", icon="mdi:harddisk-plus", native_unit_of_measurement=UnitOfDataRate.MEGABYTES_PER_SECOND, section="results", value_key="disk_write_mb_s", digits=1),
    BenchmarkSensorDescription(key="disk_read", translation_key="disk_read", name="Disk Read", icon="mdi:harddisk", native_unit_of_measurement=UnitOfDataRate.MEGABYTES_PER_SECOND, section="results", value_key="disk_read_mb_s", digits=1),
    BenchmarkSensorDescription(key="template_render", translation_key="template_render", name="Template Render", icon="mdi:code-tags", native_unit_of_measurement=UnitOfTime.MILLISECONDS, section="results", value_key="template_render_ms", digits=3),
    BenchmarkSensorDescription(key="restart_time", translation_key="restart_time", name="Restart Time", icon="mdi:restart", native_unit_of_measurement=UnitOfTime.SECONDS, section="results", value_key="restart_time_s", digits=1),
)


async def async_setup_entry(hass, entry, async_add_entities) -> None:
    device = hass.data[DOMAIN]["device"]
    entities = [BenchmarkSensor(hass, entry.entry_id, device, description) for description in SENSORS]
    async_add_entities(entities)
    hass.data.setdefault(DATA_ENTITIES, []).extend(entities)


class BenchmarkSensor(SensorEntity):
    entity_description: BenchmarkSensorDescription
    _attr_has_entity_name = True
    _attr_attribution = ATTRIBUTION
    _attr_should_poll = False

    def __init__(self, hass, entry_id: str, device_entry, description: BenchmarkSensorDescription) -> None:
        self.hass = hass
        self.entity_description = description
        self._device_entry = device_entry
        self._attr_unique_id = f"{entry_id}_{description.key}"

    @property
    def device_info(self) -> dict[str, Any]:
        return {
            "identifiers": self._device_entry.identifiers,
            "name": self._device_entry.name,
            "manufacturer": self._device_entry.manufacturer,
            "model": self._device_entry.model,
        }

    @property
    def native_value(self) -> Any:
        description = self.entity_description

        if description.value_type == "status":
            return "running" if self.hass.data.get(DATA_RUNNING) else "idle"
        if description.value_type == "progress":
            return self.hass.data.get(DATA_PROGRESS, 0)
        if description.value_type == "last_error":
            return self.hass.data.get(DATA_LAST_ERROR)
        if description.value_type == "version":
            return INTEGRATION_VERSION

        latest = self.hass.data.get(DATA_LATEST)
        if not latest:
            return None

        if description.value_type == "timestamp":
            return latest.get("timestamp")
        if description.value_type == "profile":
            return latest.get("profile")

        value = latest.get(description.section or "", {}).get(description.value_key or "")
        if value is None:
            return None
        if isinstance(value, int | float) and description.digits is not None:
            return round(value, description.digits)
        return value

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        key = self.entity_description.key
        latest = self.hass.data.get(DATA_LATEST)

        if key == "progress":
            progress = int(self.hass.data.get(DATA_PROGRESS, 0))
            filled = max(0, min(20, round(progress / 5)))
            return {
                "message": self.hass.data.get(DATA_PROGRESS_MESSAGE),
                "ascii_bar": "[" + "#" * filled + "-" * (20 - filled) + f"] {progress}%",
            }

        if key == "score" and latest:
            return {
                "profile": latest.get("profile"),
                "timestamp": latest.get("timestamp"),
                "system": latest.get("system", {}),
                "results": latest.get("results", {}),
                "scoring_formula": latest.get("results", {}).get("scoring_formula"),
                "scoring_weights": latest.get("results", {}).get("scoring_weights"),
                "scoring_normalized": latest.get("results", {}).get("scoring_normalized"),
                "last_export": self.hass.data.get(DATA_LAST_EXPORT),
                "dashboard_yaml": self.hass.data.get(DATA_DASHBOARD_YAML),
            }

        return None

# custom_components/benchmark/sensor.py

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from homeassistant.components.sensor import SensorEntity, SensorEntityDescription
from homeassistant.const import PERCENTAGE, UnitOfDataRate, UnitOfInformation, UnitOfTime
from homeassistant.helpers.entity import EntityCategory

from .const import ATTRIBUTION, DATA_DEVICE, DATA_ENTITIES, DATA_LAST_ERROR, DATA_LATEST, DATA_PROGRESS, DATA_RUNNING, DOMAIN


@dataclass(frozen=True, kw_only=True)
class BenchmarkSensorEntityDescription(SensorEntityDescription):
    section: str | None = None
    value_key: str | None = None
    digits: int | None = None
    value_type: str = "data"


SENSOR_DESCRIPTIONS: tuple[BenchmarkSensorEntityDescription, ...] = (
    BenchmarkSensorEntityDescription(
        key="status",
        translation_key="status",
        name="Status",
        icon="mdi:progress-clock",
        value_type="status",
    ),
    BenchmarkSensorEntityDescription(
        key="progress",
        translation_key="progress",
        name="Progress",
        icon="mdi:progress-helper",
        native_unit_of_measurement=PERCENTAGE,
        value_type="progress",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    BenchmarkSensorEntityDescription(
        key="last_error",
        translation_key="last_error",
        name="Last error",
        icon="mdi:alert-circle-outline",
        value_type="last_error",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    BenchmarkSensorEntityDescription(
        key="benchmark_score",
        translation_key="benchmark_score",
        name="Benchmark Score",
        icon="mdi:star",
        section="results",
        value_key="benchmark_score",
        digits=0,
    ),
    BenchmarkSensorEntityDescription(
        key="last_run",
        translation_key="last_run",
        name="Last Run",
        icon="mdi:calendar-clock",
        value_type="timestamp",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    BenchmarkSensorEntityDescription(key="install_method", name="Install Method", icon="mdi:package-variant", section="hardware", value_key="install_method", entity_category=EntityCategory.DIAGNOSTIC),
    BenchmarkSensorEntityDescription(key="ha_core", name="HA Core", icon="mdi:home-assistant", section="hardware", value_key="ha_core", entity_category=EntityCategory.DIAGNOSTIC),
    BenchmarkSensorEntityDescription(key="ha_frontend", name="HA Frontend", icon="mdi:web", section="hardware", value_key="ha_frontend", entity_category=EntityCategory.DIAGNOSTIC),
    BenchmarkSensorEntityDescription(key="ha_supervisor", name="HA Supervisor", icon="mdi:octagon-outline", section="hardware", value_key="ha_supervisor", entity_category=EntityCategory.DIAGNOSTIC),
    BenchmarkSensorEntityDescription(key="architecture", name="Architecture", icon="mdi:chip", section="hardware", value_key="architecture", entity_category=EntityCategory.DIAGNOSTIC),
    BenchmarkSensorEntityDescription(key="storage_type", name="Storage Medium", icon="mdi:harddisk", section="hardware", value_key="storage_type", entity_category=EntityCategory.DIAGNOSTIC),
    BenchmarkSensorEntityDescription(key="virtualization", name="Virtualization", icon="mdi:server-network", section="hardware", value_key="virtualization", entity_category=EntityCategory.DIAGNOSTIC),
    BenchmarkSensorEntityDescription(key="system_user", name="System User", icon="mdi:account", section="hardware", value_key="system_user", entity_category=EntityCategory.DIAGNOSTIC),
    BenchmarkSensorEntityDescription(key="boot_profile_s", name="Boot Profile", icon="mdi:clock-start", native_unit_of_measurement=UnitOfTime.SECONDS, section="hardware", value_key="boot_profile_s", digits=1, entity_category=EntityCategory.DIAGNOSTIC),
    BenchmarkSensorEntityDescription(key="ha_uptime_s", name="HA Uptime", icon="mdi:timer-outline", native_unit_of_measurement=UnitOfTime.SECONDS, section="hardware", value_key="ha_uptime_s", digits=0, entity_category=EntityCategory.DIAGNOSTIC),
    BenchmarkSensorEntityDescription(key="os_uptime_s", name="OS Uptime", icon="mdi:timer-sand", native_unit_of_measurement=UnitOfTime.SECONDS, section="hardware", value_key="os_uptime_s", digits=0, entity_category=EntityCategory.DIAGNOSTIC),
    BenchmarkSensorEntityDescription(key="process_mem_mb", name="HA RAM Usage", icon="mdi:memory", native_unit_of_measurement=UnitOfInformation.MEGABYTES, section="hardware", value_key="process_mem_mb", digits=1, entity_category=EntityCategory.DIAGNOSTIC),
    BenchmarkSensorEntityDescription(key="total_ram_mb", name="Total RAM", icon="mdi:memory", native_unit_of_measurement=UnitOfInformation.MEGABYTES, section="hardware", value_key="total_ram_mb", digits=0, entity_category=EntityCategory.DIAGNOSTIC),
    BenchmarkSensorEntityDescription(key="cpu_usage_percent", name="CPU Usage", icon="mdi:gauge", native_unit_of_measurement=PERCENTAGE, section="hardware", value_key="cpu_usage_percent", digits=1, entity_category=EntityCategory.DIAGNOSTIC),
    BenchmarkSensorEntityDescription(key="cpu_cores", name="CPU Cores", icon="mdi:cpu-64-bit", section="hardware", value_key="cpu_cores", digits=0, entity_category=EntityCategory.DIAGNOSTIC),
    BenchmarkSensorEntityDescription(key="process_threads", name="HA Threads", icon="mdi:threads", section="hardware", value_key="process_threads", digits=0, entity_category=EntityCategory.DIAGNOSTIC),
    BenchmarkSensorEntityDescription(key="ha_entities", name="HA Entities", icon="mdi:shape", section="hardware", value_key="ha_entities", digits=0, entity_category=EntityCategory.DIAGNOSTIC),
    BenchmarkSensorEntityDescription(key="ha_devices", name="HA Devices", icon="mdi:tablet-dashboard", section="hardware", value_key="ha_devices", digits=0, entity_category=EntityCategory.DIAGNOSTIC),
    BenchmarkSensorEntityDescription(key="ha_integrations", name="HA Integrations", icon="mdi:puzzle", section="hardware", value_key="ha_integrations", digits=0, entity_category=EntityCategory.DIAGNOSTIC),
    BenchmarkSensorEntityDescription(key="state_tp_ops_s", name="State Throughput", icon="mdi:swap-vertical", native_unit_of_measurement="ops/s", section="results", value_key="state_tp_ops_s", digits=1),
    BenchmarkSensorEntityDescription(key="cpu_loop_ops_s", name="CPU Loop", icon="mdi:speedometer", native_unit_of_measurement="ops/s", section="results", value_key="cpu_loop_ops_s", digits=0),
    BenchmarkSensorEntityDescription(key="cpu_stress_avg_freq_mhz", name="CPU Frequency", icon="mdi:speedometer-medium", native_unit_of_measurement="MHz", section="results", value_key="cpu_stress_avg_freq_mhz", digits=1),
    BenchmarkSensorEntityDescription(key="disk_write_mb_s", name="Disk Write", icon="mdi:download", native_unit_of_measurement=UnitOfDataRate.MEGABYTES_PER_SECOND, section="results", value_key="disk_write_mb_s", digits=1),
    BenchmarkSensorEntityDescription(key="disk_read_mb_s", name="Disk Read", icon="mdi:upload", native_unit_of_measurement=UnitOfDataRate.MEGABYTES_PER_SECOND, section="results", value_key="disk_read_mb_s", digits=1),
    BenchmarkSensorEntityDescription(key="eventbus_p50_ms", name="EventBus P50", icon="mdi:bus-clock", native_unit_of_measurement=UnitOfTime.MILLISECONDS, section="results", value_key="eventbus_p50_ms", digits=2),
    BenchmarkSensorEntityDescription(key="eventbus_p95_ms", name="EventBus P95", icon="mdi:bus", native_unit_of_measurement=UnitOfTime.MILLISECONDS, section="results", value_key="eventbus_p95_ms", digits=2),
    BenchmarkSensorEntityDescription(key="automation_p95_ms", name="Automation P95", icon="mdi:flash", native_unit_of_measurement=UnitOfTime.MILLISECONDS, section="results", value_key="automation_p95_ms", digits=2),
    BenchmarkSensorEntityDescription(key="service_call_avg_ms", name="Service Call Average", icon="mdi:service-toolbox", native_unit_of_measurement=UnitOfTime.MILLISECONDS, section="results", value_key="service_call_avg_ms", digits=2),
    BenchmarkSensorEntityDescription(key="service_call_p95_ms", name="Service Call P95", icon="mdi:service-alert", native_unit_of_measurement=UnitOfTime.MILLISECONDS, section="results", value_key="service_call_p95_ms", digits=2),
    BenchmarkSensorEntityDescription(key="loop_latency_p95_ms", name="Loop Latency P95", icon="mdi:alpha-l-circle", native_unit_of_measurement=UnitOfTime.MILLISECONDS, section="results", value_key="loop_latency_p95_ms", digits=2),
    BenchmarkSensorEntityDescription(key="template_render_ms", name="Template Render", icon="mdi:code-tags", native_unit_of_measurement=UnitOfTime.MILLISECONDS, section="results", value_key="template_render_ms", digits=2),
)


async def async_setup_entry(hass, entry, async_add_entities):
    device = hass.data[DATA_DEVICE]
    entities = [BenchmarkSensor(hass, entry.entry_id, device, description) for description in SENSOR_DESCRIPTIONS]
    async_add_entities(entities)
    hass.data.setdefault(DATA_ENTITIES, []).extend(entities)


class BenchmarkSensor(SensorEntity):
    entity_description: BenchmarkSensorEntityDescription
    _attr_has_entity_name = True
    _attr_attribution = ATTRIBUTION
    _attr_should_poll = False

    def __init__(self, hass, entry_id: str, device_entry, description: BenchmarkSensorEntityDescription) -> None:
        self.hass = hass
        self.entity_description = description
        self._device = device_entry
        self._attr_unique_id = f"{entry_id}_{description.key}"

    @property
    def device_info(self):
        return {
            "identifiers": self._device.identifiers,
            "name": self._device.name,
            "manufacturer": self._device.manufacturer,
            "model": self._device.model,
        }

    @property
    def native_value(self):
        description = self.entity_description

        if description.value_type == "status":
            return "running" if self.hass.data.get(DATA_RUNNING) else "idle"

        if description.value_type == "progress":
            return self.hass.data.get(DATA_PROGRESS, 0)

        if description.value_type == "last_error":
            return self.hass.data.get(DATA_LAST_ERROR)

        latest = self.hass.data.get(DATA_LATEST)
        if not latest:
            return None

        if description.value_type == "timestamp":
            return latest.get("timestamp")

        section = description.section
        value_key = description.value_key
        if not section or not value_key:
            return None

        value = latest.get(section, {}).get(value_key)
        if value is None:
            return None

        if description.digits is not None and isinstance(value, (int, float)):
            return round(value, description.digits)

        return value

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        latest = self.hass.data.get(DATA_LATEST)
        if self.entity_description.key != "benchmark_score" or not latest:
            return None

        return {
            "timestamp": latest.get("timestamp"),
            "hardware": latest.get("hardware", {}),
            "results": latest.get("results", {}),
        }

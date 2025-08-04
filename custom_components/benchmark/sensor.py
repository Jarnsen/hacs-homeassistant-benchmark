# custom_components/benchmark/sensor.py

import os
import json
from homeassistant.helpers.entity import Entity
from .const import DOMAIN, DATA_FILE

SENSOR_DEFS = [
    # Hardware-Sektion
    ("hardware", "install_method",     "Installationsmethode", None,   "mdi:package-variant",     None),
    ("hardware", "ha_core",            "HA Core",             None,   "mdi:home-assistant",      None),
    ("hardware", "ha_frontend",        "HA Frontend",         None,   "mdi:web",                 None),
    ("hardware", "ha_supervisor",      "HA Supervisor",       None,   "mdi:octagon-outline",     None),
    ("hardware", "boot_profile_s",     "Boot-Profil",         "s",    "mdi:clock-start",         1),
    ("hardware", "ha_restart_s",       "HA Restart Dauer",    "s",    "mdi:restart",            1),
    ("hardware", "os_system",          "OS System",           None,   "mdi:desktop-tower",       None),
    ("hardware", "os_version",         "OS Version",          None,   "mdi:information-outline",None),
    ("hardware", "os_uptime_s",        "OS-Uptime",           "s",    "mdi:timer-sand",          0),
    ("hardware", "architecture",       "Architektur",         None,   "mdi:chip",                None),
    ("hardware", "storage_type",       "Speichermedium",      None,   "mdi:harddisk",            None),
    ("hardware", "virtualization",     "Virtualisierung",     None,   "mdi:server-network",      None),
    ("hardware", "process_mem_mb",     "HA RAM-Usage",        "MB",   "mdi:memory",              1),
    ("hardware", "total_ram_mb",       "Total RAM",           "MB",   "mdi:memory",              0),
    ("hardware", "cpu_usage_percent",  "CPU-Auslastung",      "%",    "mdi:gauge",               1),
    ("hardware", "cpu_cores",          "CPU-Cores",           "cores","mdi:cpu-64-bit",        0),
    ("hardware", "process_threads",    "HA-Threads",          None,   "mdi:threads",             0),
    ("hardware", "system_user",        "System-User",         None,   "mdi:account",             None),
    ("hardware", "ha_entities",        "HA-Entities",         None,   "mdi:shape",               0),
    ("hardware", "ha_devices",         "HA-Geräte",           None,   "mdi:tablet-dashboard",    0),
    ("hardware", "ha_integrations",    "HA-Integrationen",    None,   "mdi:puzzle",              0),
    ("hardware", "ha_uptime_s",        "HA-Uptime",           "s",    "mdi:timer-outline",       1),

    # Performance-Sektion
    ("results",  "state_tp_ops_s",     "State-TP",            "ops/s","mdi:swap-vertical",    1),
    ("results",  "cpu_stress_avg_freq_mhz","CPU-Freq (avg)",  "MHz",  "mdi:speedometer",         1),
    ("results",  "disk_write_ms",      "Disk-Write (50 MB)",   "ms",   "mdi:download",            1),
    ("results",  "disk_read_ms",       "Disk-Read (50 MB)",    "ms",   "mdi:upload",              1),
    ("results",  "eventbus_p95_ms",    "EventBus P95",        "ms",   "mdi:bus",                 1),
    ("results",  "automation_p95_ms",  "Automation P95",      "ms",   "mdi:flash",               1),
    ("results",  "api_p50_ms",         "API P50",             "ms",   "mdi:web-check",           1),
    ("results",  "api_p95_ms",         "API P95",             "ms",   "mdi:web",                 1),
    ("results",  "ping_p50_ms",        "Ping P50",            "ms",   "mdi:lan",                 1),
    ("results",  "ping_p95_ms",        "Ping P95",            "ms",   "mdi:lan-connect",         1),
    ("results",  "service_call_p95_ms","Service-Call P95",    "ms",   "mdi:service-alert",       1),
    ("results",  "recorder_commit_ms", "Recorder-Commit",     "ms",   "mdi:database",            1),
    ("results",  "loop_latency_p95_ms","Loop-Latency P95",    "ms",   "mdi:alpha-l-circle",      1),
    ("results",  "template_render_ms", "Template-Render",     "ms",   "mdi:code-tags",           1),

    # Gesamt-Score
    ("results",  "benchmark_score",    "Benchmark-Score",     None,   "mdi:star",                2),
]

async def async_setup_entry(hass, entry, async_add_entities):
    history = hass.config.path(DATA_FILE)
    device = hass.data[f"{DOMAIN}_device"]

    entities = [
        BenchmarkSensor(device, history, section, key, name, unit, icon, digits)
        for section, key, name, unit, icon, digits in SENSOR_DEFS
    ]

    async_add_entities(entities, True)
    hass.data.setdefault(f"{DOMAIN}_entities", []).extend(entities)

class BenchmarkSensor(Entity):
    def __init__(self, device_entry, history_path, section, key, name, unit, icon, digits):
        self._device = device_entry
        self._history = history_path
        self._section = section
        self._key = key
        self._name = name
        self._unit = unit
        self._icon = icon
        self._digits = digits
        self._state = None

    @property
    def available(self):
        return True

    @property
    def device_info(self):
        return {
            "identifiers":  self._device.identifiers,
            "name":         self._device.name,
            "manufacturer": self._device.manufacturer,
            "model":        self._device.model,
        }

    @property
    def name(self):
        return f"Benchmark {self._name}"

    @property
    def unique_id(self):
        return f"benchmark_{self._section}_{self._key}"

    @property
    def icon(self):
        return self._icon

    @property
    def unit_of_measurement(self):
        return self._unit

    @property
    def state(self):
        return self._state if self._state is not None else "n/a"

    def update(self):
        if not os.path.exists(self._history):
            self._state = None
            return
        try:
            with open(self._history) as fp:
                data = json.load(fp)
            val = data[-1].get(self._section, {}).get(self._key)
            if val is None:
                self._state = None
            elif self._digits is not None and isinstance(val, (int, float)):
                self._state = round(val, self._digits)
            else:
                self._state = val
        except Exception:
            self._state = None

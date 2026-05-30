# custom_components/benchmark/diagnostics.py

from __future__ import annotations

from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import DATA_BENCHMARK_ID, DATA_LAST_ERROR, DATA_LATEST, DATA_PROGRESS, DATA_RUNNING, INTEGRATION_VERSION


async def async_get_config_entry_diagnostics(hass: HomeAssistant, entry: ConfigEntry) -> dict[str, Any]:
    latest = hass.data.get(DATA_LATEST) or {}
    return {
        "integration_version": INTEGRATION_VERSION,
        "entry": {
            "title": entry.title,
            "domain": entry.domain,
        },
        "runtime": {
            "running": hass.data.get(DATA_RUNNING, False),
            "progress": hass.data.get(DATA_PROGRESS, 0),
            "last_error": hass.data.get(DATA_LAST_ERROR),
            "benchmark_id_present": bool(hass.data.get(DATA_BENCHMARK_ID)),
        },
        "latest": {
            "timestamp": latest.get("timestamp"),
            "hardware": latest.get("hardware", {}),
            "results": latest.get("results", {}),
            "leaderboard": latest.get("leaderboard", {}),
        },
    }

from __future__ import annotations

from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import (
    DATA_LAST_ERROR,
    DATA_LATEST,
    DATA_PROGRESS,
    DATA_PROGRESS_MESSAGE,
    DATA_RUNNING,
    INTEGRATION_VERSION,
)


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
            "progress_message": hass.data.get(DATA_PROGRESS_MESSAGE),
            "last_error": hass.data.get(DATA_LAST_ERROR),
        },
        "latest": {
            "timestamp": latest.get("timestamp"),
            "profile": latest.get("profile"),
            "system": latest.get("system", {}),
            "results": latest.get("results", {}),
        },
    }

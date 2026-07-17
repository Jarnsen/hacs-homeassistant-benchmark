"""Diagnostics for Home Assistant Performance Benchmark."""

from __future__ import annotations

from typing import Any

from homeassistant.core import HomeAssistant

from .const import INTEGRATION_VERSION, PROTOCOL_VERSION
from .runtime import BenchmarkConfigEntry


async def async_get_config_entry_diagnostics(
    _hass: HomeAssistant,
    entry: BenchmarkConfigEntry,
) -> dict[str, Any]:
    """Return privacy-safe diagnostics."""
    runtime = entry.runtime_data
    latest = runtime.latest or {}
    return {
        "integration_version": INTEGRATION_VERSION,
        "protocol_version": PROTOCOL_VERSION,
        "entry": {
            "title": entry.title,
            "version": entry.version,
            "options": dict(entry.options),
        },
        "runtime": {
            "status": runtime.status,
            "running": runtime.running,
            "progress": runtime.progress,
            "progress_message": runtime.progress_message,
            "last_error": runtime.last_error,
            "history_count": len(runtime.history),
            "legacy_history_count": len(runtime.legacy_history),
            "pending_restart": bool(runtime.pending_restart),
        },
        "latest": {
            "schema": latest.get("schema"),
            "timestamp": latest.get("timestamp"),
            "protocol_version": latest.get("protocol_version"),
            "score_version": latest.get("score_version"),
            "protocol": latest.get("protocol", {}),
            "profile": latest.get("profile"),
            "duration_s": latest.get("duration_s"),
            "scores": latest.get("scores", {}),
            "measurements": latest.get("measurements", {}),
            "system": latest.get("system", {}),
            "secondary": latest.get("secondary", {}),
            "validity": latest.get("validity", {}),
        },
    }

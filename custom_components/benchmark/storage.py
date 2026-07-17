"""Persistent storage and export helpers."""

from __future__ import annotations

import csv
import json
import logging
from pathlib import Path
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store

from .const import (
    LEGACY_HISTORY_FILE,
    LEGACY_META_FILE,
    LEGACY_RESTART_FILE,
    MAX_LEGACY_HISTORY_ENTRIES,
    STORAGE_KEY_PREFIX,
    STORAGE_VERSION,
)

_LOGGER = logging.getLogger(__name__)

StoredData = dict[str, Any]
BenchmarkStore = Store[StoredData]


def default_stored_data() -> StoredData:
    """Return a new storage document."""
    return {
        "history": [],
        "legacy_history": [],
        "pending_restart": None,
    }


def _read_json(path: str, default: Any) -> Any:
    try:
        with Path(path).open(encoding="utf-8") as file:
            return json.load(file)
    except (FileNotFoundError, OSError, json.JSONDecodeError):
        return default


def _remove_files(paths: list[str]) -> None:
    for path in paths:
        try:
            Path(path).unlink()
        except FileNotFoundError:
            pass
        except OSError:
            _LOGGER.warning("Could not remove migrated legacy file %s", path)


async def async_load_store(
    hass: HomeAssistant,
    entry_id: str,
) -> tuple[BenchmarkStore, StoredData]:
    """Load v3 storage and migrate legacy JSON files once."""
    store: BenchmarkStore = Store(
        hass,
        STORAGE_VERSION,
        f"{STORAGE_KEY_PREFIX}.{entry_id}",
        atomic_writes=True,
        private=True,
    )
    stored = await store.async_load()
    if isinstance(stored, dict):
        data = default_stored_data()
        data.update(stored)
        if not isinstance(data["history"], list):
            data["history"] = []
        if not isinstance(data["legacy_history"], list):
            data["legacy_history"] = []
        return store, data

    history_path = hass.config.path(LEGACY_HISTORY_FILE)
    restart_path = hass.config.path(LEGACY_RESTART_FILE)
    meta_path = hass.config.path(LEGACY_META_FILE)
    legacy_history = await hass.async_add_executor_job(
        _read_json,
        history_path,
        [],
    )
    legacy_restart = await hass.async_add_executor_job(
        _read_json,
        restart_path,
        {},
    )

    data = default_stored_data()
    if isinstance(legacy_history, list):
        data["legacy_history"] = legacy_history[-MAX_LEGACY_HISTORY_ENTRIES:]
    if (
        isinstance(legacy_restart, dict)
        and legacy_restart.get("state") == "pending"
        and isinstance(legacy_restart.get("started_at"), int | float)
    ):
        data["pending_restart"] = {
            "requested_at": float(legacy_restart["started_at"]),
            "profile": legacy_restart.get("profile", "standard"),
            "migrated_from_v2": True,
        }

    await store.async_save(data)
    await hass.async_add_executor_job(
        _remove_files,
        [history_path, restart_path, meta_path],
    )
    return store, data


def write_json(path: str, data: Any) -> None:
    """Atomically write a JSON export."""
    target = Path(path)
    temporary = target.with_suffix(f"{target.suffix}.tmp")
    temporary.write_text(
        json.dumps(data, ensure_ascii=False, indent=2, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    temporary.replace(target)


def write_csv(path: str, history: list[dict[str, Any]]) -> None:
    """Atomically write a compact result history CSV."""
    target = Path(path)
    temporary = target.with_suffix(f"{target.suffix}.tmp")
    fields = [
        "timestamp",
        "profile",
        "ha_performance_score",
        "ha_core_score",
        "fluidity_score",
        "confidence",
        "event_loop_idle_p95_ms",
        "event_loop_loaded_p95_ms",
        "state_machine_p95_ms",
        "event_bus_p95_ms",
        "service_calls_p95_ms",
        "template_render_p95_ms",
        "restart_recovery_time_s",
        "home_assistant_version",
        "architecture",
        "cpu_model",
        "device_model",
        "cpu_cores_logical",
        "ram_total_mb",
        "entity_count",
    ]
    with temporary.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fields)
        writer.writeheader()
        for entry in history:
            scores = entry.get("scores", {})
            measurements = entry.get("measurements", {})
            system = entry.get("system", {})
            writer.writerow(
                {
                    "timestamp": entry.get("timestamp"),
                    "profile": entry.get("profile"),
                    "ha_performance_score": scores.get("ha_performance_score"),
                    "ha_core_score": scores.get("ha_core_score"),
                    "fluidity_score": scores.get("fluidity_score"),
                    "confidence": entry.get("validity", {}).get("confidence"),
                    "event_loop_idle_p95_ms": measurements.get(
                        "event_loop_idle", {}
                    ).get("p95_ms"),
                    "event_loop_loaded_p95_ms": measurements.get(
                        "event_loop_loaded", {}
                    ).get("p95_ms"),
                    "state_machine_p95_ms": measurements.get("state_machine", {}).get(
                        "p95_ms"
                    ),
                    "event_bus_p95_ms": measurements.get("event_bus", {}).get("p95_ms"),
                    "service_calls_p95_ms": measurements.get("service_calls", {}).get(
                        "p95_ms"
                    ),
                    "template_render_p95_ms": measurements.get(
                        "template_render", {}
                    ).get("p95_ms"),
                    "restart_recovery_time_s": entry.get("secondary", {}).get(
                        "restart_recovery_time_s"
                    ),
                    "home_assistant_version": system.get("home_assistant_version"),
                    "architecture": system.get("architecture"),
                    "cpu_model": system.get("cpu_model"),
                    "device_model": system.get("device_model"),
                    "cpu_cores_logical": system.get("cpu_cores_logical"),
                    "ram_total_mb": system.get("ram_total_mb"),
                    "entity_count": system.get("entity_count"),
                }
            )
    temporary.replace(target)

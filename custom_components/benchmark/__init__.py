# custom_components/benchmark/__init__.py

from __future__ import annotations

import json
import os
import time
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EVENT_HOMEASSISTANT_STARTED, Platform
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import device_registry

from .const import DATA_FILE, DOMAIN
from .services import compute_score, run_benchmark_async, run_benchmark_sync

PLATFORMS: list[Platform] = [Platform.SENSOR, Platform.BUTTON]

DATA_DEVICE = f"{DOMAIN}_device"
DATA_ENTITIES = f"{DOMAIN}_entities"
DATA_LATEST = f"{DOMAIN}_latest"
DATA_RUNNING = f"{DOMAIN}_running"


def _read_history(path: str) -> list[dict[str, Any]]:
    if not os.path.exists(path):
        return []

    try:
        with open(path, encoding="utf-8") as fp:
            data = json.load(fp)
    except (OSError, json.JSONDecodeError):
        return []

    return data if isinstance(data, list) else []


def _write_history(path: str, data: list[dict[str, Any]]) -> None:
    tmp_path = f"{path}.tmp"
    with open(tmp_path, "w", encoding="utf-8") as fp:
        json.dump(data, fp, ensure_ascii=False, indent=2)
    os.replace(tmp_path, path)


def _append_history(path: str, entry: dict[str, Any], max_entries: int = 50) -> list[dict[str, Any]]:
    data = _read_history(path)
    data.append(entry)
    data = data[-max_entries:]
    _write_history(path, data)
    return data


async def _notify(hass: HomeAssistant, message: str) -> None:
    await hass.services.async_call(
        "persistent_notification",
        "create",
        {"title": "Benchmark", "message": message},
        blocking=False,
    )


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    path = hass.config.path(DATA_FILE)
    history = await hass.async_add_executor_job(_read_history, path)
    hass.data[DATA_LATEST] = history[-1] if history else None

    hass.data.setdefault("benchmark_start_time", time.time())
    hass.bus.async_listen_once(
        EVENT_HOMEASSISTANT_STARTED,
        lambda event: hass.data.__setitem__("benchmark_ha_ready", time.time()),
    )
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    hass.data.setdefault(DOMAIN, {})
    hass.data.setdefault(DATA_ENTITIES, [])
    hass.data.setdefault(DATA_RUNNING, False)

    dr = device_registry.async_get(hass)
    device = dr.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, entry.entry_id)},
        name="Benchmark",
        manufacturer="Home Assistant",
        model="Benchmark",
    )
    hass.data[DATA_DEVICE] = device

    async def handle_start(call: ServiceCall) -> None:
        if hass.data.get(DATA_RUNNING):
            await _notify(hass, "Benchmark läuft bereits.")
            return

        hass.data[DATA_RUNNING] = True
        try:
            await _notify(hass, "Benchmark gestartet …")

            sync = await hass.async_add_executor_job(run_benchmark_sync, hass)
            async_results = await run_benchmark_async(hass)

            merged = {**sync["results"], **async_results}
            merged["benchmark_score"] = compute_score(merged, sync["hardware"])

            result_entry = {
                "timestamp": sync["timestamp"],
                "hardware": sync["hardware"],
                "results": merged,
            }

            history_path = hass.config.path(DATA_FILE)
            await hass.async_add_executor_job(_append_history, history_path, result_entry)
            hass.data[DATA_LATEST] = result_entry

            for entity in hass.data.get(DATA_ENTITIES, []):
                entity.async_write_ha_state()

            await _notify(
                hass,
                f"Benchmark abgeschlossen. Score: {merged['benchmark_score']}",
            )
        except Exception as err:  # noqa: BLE001 - keep HA usable and show the error
            await _notify(hass, f"Benchmark fehlgeschlagen: {err}")
            raise
        finally:
            hass.data[DATA_RUNNING] = False

    hass.services.async_register(DOMAIN, "start", handle_start)
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    if unload_ok:
        hass.services.async_remove(DOMAIN, "start")
        hass.data.pop(DATA_DEVICE, None)
        hass.data.pop(DATA_ENTITIES, None)
        hass.data.pop(DATA_RUNNING, None)

    return unload_ok

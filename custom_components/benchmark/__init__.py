# custom_components/benchmark/__init__.py

from __future__ import annotations

import hashlib
import json
import os
import time
import urllib.parse
import uuid
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EVENT_HOMEASSISTANT_STARTED, Platform
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import device_registry

from .const import (
    DATA_BENCHMARK_ID,
    DATA_DEVICE,
    DATA_ENTITIES,
    DATA_FILE,
    DATA_LAST_ERROR,
    DATA_LAST_LEADERBOARD_PAYLOAD,
    DATA_LATEST,
    DATA_PROGRESS,
    DATA_RUNNING,
    DATA_SUBMIT_URL,
    DOMAIN,
    GITHUB_REPOSITORY,
    ID_FILE,
    INTEGRATION_VERSION,
    MAX_HISTORY_ENTRIES,
)
from .services import compute_score, run_benchmark_async, run_benchmark_sync

PLATFORMS: list[Platform] = [Platform.SENSOR, Platform.BUTTON]
RESTART_STATE_FILE = ".benchmark_restart.json"


def _read_json_file(path: str, default: Any) -> Any:
    if not os.path.exists(path):
        return default
    try:
        with open(path, encoding="utf-8") as fp:
            return json.load(fp)
    except (OSError, json.JSONDecodeError):
        return default


def _write_json_file(path: str, data: Any) -> None:
    tmp_path = f"{path}.tmp"
    with open(tmp_path, "w", encoding="utf-8") as fp:
        json.dump(data, fp, ensure_ascii=False, indent=2)
    os.replace(tmp_path, path)


def _read_history(path: str) -> list[dict[str, Any]]:
    data = _read_json_file(path, [])
    return data if isinstance(data, list) else []


def _append_history(path: str, entry: dict[str, Any], max_entries: int = MAX_HISTORY_ENTRIES) -> list[dict[str, Any]]:
    data = _read_history(path)
    data.append(entry)
    data = data[-max_entries:]
    _write_json_file(path, data)
    return data


def _load_or_create_benchmark_id(path: str) -> str:
    try:
        if os.path.exists(path):
            with open(path, encoding="utf-8") as fp:
                existing = fp.read().strip()
                if existing:
                    return existing
        new_id = uuid.uuid4().hex
        with open(path, "w", encoding="utf-8") as fp:
            fp.write(new_id)
        return new_id
    except OSError:
        return uuid.uuid4().hex


def _build_leaderboard_payload(benchmark_id: str, result: dict[str, Any]) -> dict[str, Any]:
    hardware = result.get("hardware", {})
    results = result.get("results", {})
    hardware_fingerprint_source = "|".join(
        str(hardware.get(key, ""))
        for key in (
            "install_method",
            "architecture",
            "os_system",
            "storage_type",
            "virtualization",
            "cpu_cores",
            "total_ram_mb",
        )
    )

    return {
        "schema_version": 1,
        "integration_version": INTEGRATION_VERSION,
        "benchmark_id": benchmark_id,
        "hardware_fingerprint": hashlib.sha256(hardware_fingerprint_source.encode("utf-8")).hexdigest(),
        "timestamp": result.get("timestamp"),
        "score": results.get("benchmark_score"),
        "hardware": {
            "install_method": hardware.get("install_method"),
            "ha_core": hardware.get("ha_core"),
            "ha_supervisor": hardware.get("ha_supervisor"),
            "architecture": hardware.get("architecture"),
            "storage_type": hardware.get("storage_type"),
            "virtualization": hardware.get("virtualization"),
            "cpu_cores": hardware.get("cpu_cores"),
            "total_ram_mb": hardware.get("total_ram_mb"),
            "ha_entities": hardware.get("ha_entities"),
            "ha_devices": hardware.get("ha_devices"),
            "ha_integrations": hardware.get("ha_integrations"),
        },
        "results": results,
    }


def _build_submit_url(payload: dict[str, Any]) -> str:
    body = "## Benchmark payload\n\n```json\n" + json.dumps(payload, ensure_ascii=False, indent=2) + "\n```\n"
    query = urllib.parse.urlencode(
        {
            "title": f"Benchmark result: {payload.get('score', 'unknown')}",
            "body": body,
            "labels": "benchmark-result",
        }
    )
    return f"https://github.com/{GITHUB_REPOSITORY}/issues/new?{query}"


def _load_restart_result(hass: HomeAssistant) -> float | None:
    path = hass.config.path(RESTART_STATE_FILE)
    state = _read_json_file(path, {})
    if not isinstance(state, dict) or state.get("state") != "pending":
        return None
    started_at = state.get("started_at")
    if not isinstance(started_at, (int, float)):
        return None
    try:
        os.remove(path)
    except OSError:
        pass
    return max(round(time.time() - started_at, 1), 0)


async def _notify(hass: HomeAssistant, message: str) -> None:
    await hass.services.async_call(
        "persistent_notification",
        "create",
        {"title": "Benchmark", "message": message},
        blocking=False,
    )


def _update_entities(hass: HomeAssistant) -> None:
    for entity in hass.data.get(DATA_ENTITIES, []):
        entity.async_write_ha_state()


async def _set_progress(hass: HomeAssistant, value: int) -> None:
    hass.data[DATA_PROGRESS] = value
    _update_entities(hass)


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    history_path = hass.config.path(DATA_FILE)
    history = await hass.async_add_executor_job(_read_history, history_path)
    latest = history[-1] if history else None

    hass.data[DATA_LATEST] = latest
    hass.data.setdefault(DATA_PROGRESS, 0)
    hass.data.setdefault(DATA_LAST_ERROR, None)
    hass.data[DATA_BENCHMARK_ID] = await hass.async_add_executor_job(
        _load_or_create_benchmark_id, hass.config.path(ID_FILE)
    )
    hass.data[DATA_LAST_LEADERBOARD_PAYLOAD] = latest.get("leaderboard") if latest else None
    hass.data[DATA_SUBMIT_URL] = _build_submit_url(hass.data[DATA_LAST_LEADERBOARD_PAYLOAD]) if latest and latest.get("leaderboard") else None

    restart_seconds = await hass.async_add_executor_job(_load_restart_result, hass)
    if restart_seconds is not None:
        if latest:
            latest.setdefault("results", {})["ha_restart_s"] = restart_seconds
            latest["leaderboard"] = _build_leaderboard_payload(hass.data[DATA_BENCHMARK_ID], latest)
            await hass.async_add_executor_job(_append_history, history_path, latest)
            hass.data[DATA_LATEST] = latest
            hass.data[DATA_LAST_LEADERBOARD_PAYLOAD] = latest["leaderboard"]
            hass.data[DATA_SUBMIT_URL] = _build_submit_url(latest["leaderboard"])
        await _notify(hass, f"Restart-Benchmark abgeschlossen: {restart_seconds} s")

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
    hass.data.setdefault(DATA_PROGRESS, 0)
    hass.data.setdefault(DATA_LAST_ERROR, None)
    hass.data.setdefault(DATA_BENCHMARK_ID, await hass.async_add_executor_job(_load_or_create_benchmark_id, hass.config.path(ID_FILE)))

    dr = device_registry.async_get(hass)
    device = dr.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, entry.entry_id)},
        name="Benchmark",
        manufacturer="Home Assistant",
        model="Benchmark",
        sw_version=INTEGRATION_VERSION,
    )
    hass.data[DATA_DEVICE] = device

    async def handle_start(call: ServiceCall) -> None:
        if hass.data.get(DATA_RUNNING):
            await _notify(hass, "Benchmark läuft bereits.")
            return

        hass.data[DATA_RUNNING] = True
        hass.data[DATA_LAST_ERROR] = None
        await _set_progress(hass, 5)

        try:
            await _notify(hass, "Benchmark gestartet …")

            await _set_progress(hass, 20)
            sync = await hass.async_add_executor_job(run_benchmark_sync, hass)

            await _set_progress(hass, 65)
            async_results = await run_benchmark_async(hass)

            await _set_progress(hass, 85)
            merged = {**sync["results"], **async_results}
            merged["benchmark_score"] = compute_score(merged, sync["hardware"])

            result_entry = {
                "timestamp": sync["timestamp"],
                "hardware": sync["hardware"],
                "results": merged,
            }
            result_entry["leaderboard"] = _build_leaderboard_payload(hass.data[DATA_BENCHMARK_ID], result_entry)

            history_path = hass.config.path(DATA_FILE)
            await hass.async_add_executor_job(_append_history, history_path, result_entry)
            hass.data[DATA_LATEST] = result_entry
            hass.data[DATA_LAST_LEADERBOARD_PAYLOAD] = result_entry["leaderboard"]
            hass.data[DATA_SUBMIT_URL] = _build_submit_url(result_entry["leaderboard"])

            await _set_progress(hass, 100)
            await _notify(
                hass,
                f"Benchmark abgeschlossen. Score: {merged['benchmark_score']}",
            )
        except Exception as err:  # noqa: BLE001 - keep HA usable and show the error
            hass.data[DATA_LAST_ERROR] = str(err)
            await _set_progress(hass, 0)
            await _notify(hass, f"Benchmark fehlgeschlagen: {err}")
            raise
        finally:
            hass.data[DATA_RUNNING] = False
            _update_entities(hass)

    async def handle_restart(call: ServiceCall) -> None:
        state = {"state": "pending", "started_at": time.time(), "integration_version": INTEGRATION_VERSION}
        await hass.async_add_executor_job(_write_json_file, hass.config.path(RESTART_STATE_FILE), state)
        await _notify(hass, "Restart-Benchmark vorbereitet. Home Assistant startet jetzt neu …")
        await hass.services.async_call("homeassistant", "restart", {}, blocking=True)

    hass.services.async_register(DOMAIN, "start", handle_start)
    hass.services.async_register(DOMAIN, "restart_benchmark", handle_restart)
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    if unload_ok:
        hass.services.async_remove(DOMAIN, "start")
        hass.services.async_remove(DOMAIN, "restart_benchmark")
        hass.data.pop(DATA_DEVICE, None)
        hass.data.pop(DATA_ENTITIES, None)
        hass.data.pop(DATA_RUNNING, None)

    return unload_ok

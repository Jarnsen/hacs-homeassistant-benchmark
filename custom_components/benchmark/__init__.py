from __future__ import annotations

import datetime as dt
import logging
import os
import time

import voluptuous as vol
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EVENT_HOMEASSISTANT_STARTED, Platform
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import device_registry, entity_registry as er

from .const import (
    DATA_DASHBOARD_YAML,
    DATA_ENTITIES,
    DATA_FILE,
    DATA_ISSUE_URL,
    DATA_LAST_ERROR,
    DATA_LAST_EXPORT,
    DATA_LAST_WORLDLIST_EXPORT,
    DATA_LATEST,
    DATA_PROGRESS,
    DATA_PROGRESS_MESSAGE,
    DATA_REPOSITORY_URL,
    DATA_RUNNING,
    DOMAIN,
    EXPORT_CSV_FILE,
    EXPORT_JSON_FILE,
    GITHUB_ISSUES_URL,
    GITHUB_REPOSITORY_URL,
    INTEGRATION_VERSION,
    MAX_HISTORY_ENTRIES,
    META_FILE,
    PROFILES,
    RESTART_STATE_FILE,
    SCORE_WARNING_LIMIT,
    WORLDLIST_EXPORT_FILE,
)
from .dashboard import build_dashboard_yaml
from .engine import run_benchmark
from .storage import atomic_write_json, read_json

_LOGGER = logging.getLogger(__name__)
PLATFORMS: list[Platform] = [Platform.SENSOR, Platform.BUTTON]

LEGACY_SENSOR_KEYS: tuple[str, ...] = (
    "install_method", "ha_core", "ha_frontend", "ha_supervisor", "architecture", "storage_type",
    "virtualization", "system_user", "boot_profile_s", "ha_restart_s", "ha_uptime_s", "os_uptime_s",
    "process_mem_mb", "total_ram_mb", "cpu_usage_percent", "cpu_cores", "process_threads",
    "ha_entities", "ha_devices", "ha_integrations", "state_tp_ops_s", "cpu_loop_ops_s",
    "cpu_stress_avg_freq_mhz", "disk_write_mb_s", "disk_read_mb_s", "eventbus_p50_ms",
    "eventbus_p95_ms", "automation_p95_ms", "service_call_avg_ms", "service_call_p95_ms",
    "loop_latency_p95_ms",
)
LEGACY_BUTTON_KEYS: tuple[str, ...] = ("start_button", "restart_button")


def _load_class(entity_count: int | None) -> str:
    if entity_count is None:
        return "unknown"
    if entity_count < 250:
        return "small"
    if entity_count < 750:
        return "medium"
    if entity_count < 1500:
        return "large"
    return "very_large"


def _build_worldlist_payload(latest: dict | None) -> dict:
    latest = latest if isinstance(latest, dict) else {}
    system = latest.get("system", {}) if isinstance(latest.get("system", {}), dict) else {}
    results = latest.get("results", {}) if isinstance(latest.get("results", {}), dict) else {}
    entity_count = system.get("entity_count")

    return {
        "schema": "ha_real_world_benchmark_worldlist_v1",
        "exported_at": dt.datetime.now(dt.UTC).isoformat(),
        "benchmark": {
            "name": "Home Assistant Real World Benchmark",
            "version": INTEGRATION_VERSION,
            "profile": latest.get("profile"),
            "timestamp": latest.get("timestamp"),
            "score": results.get("benchmark_score"),
            "scoring_formula": results.get("scoring_formula"),
            "scoring_weights": results.get("scoring_weights"),
            "scoring_normalized": results.get("scoring_normalized"),
        },
        "system_class": {
            "architecture": system.get("architecture"),
            "os": system.get("os"),
            "python_version": system.get("python_version"),
            "cpu_cores_physical": system.get("cpu_cores_physical"),
            "cpu_cores_logical": system.get("cpu_cores_logical"),
            "ram_total_mb": system.get("ram_total_mb"),
            "disk_total_mb": system.get("disk_total_mb"),
            "disk_free_mb": system.get("disk_free_mb"),
        },
        "home_assistant_load": {
            "entity_count": entity_count,
            "load_class": _load_class(entity_count if isinstance(entity_count, int) else None),
            "process_memory_mb": system.get("process_memory_mb"),
            "process_threads": system.get("process_threads"),
        },
        "results": {
            "cpu_ops_s": results.get("cpu_ops_s"),
            "disk_write_mb_s": results.get("disk_write_mb_s"),
            "disk_read_mb_s": results.get("disk_read_mb_s"),
            "template_render_ms": results.get("template_render_ms"),
            "restart_time_s": results.get("restart_time_s"),
            "disk_test_size_mb": results.get("disk_test_size_mb"),
            "outlier_method": results.get("disk_outlier_method") or results.get("cpu_outlier_method"),
        },
        "privacy": {
            "anonymous": True,
            "excluded": [
                "entity_ids", "device_names", "ip_addresses", "hostnames", "usernames", "tokens",
                "config_path", "integration_config", "custom_entity_names",
            ],
        },
    }


def _cleanup_legacy_entities(hass: HomeAssistant, entry: ConfigEntry) -> None:
    registry = er.async_get(hass)
    removed = 0

    for key in LEGACY_SENSOR_KEYS:
        entity_id = registry.async_get_entity_id("sensor", DOMAIN, f"{entry.entry_id}_{key}")
        if entity_id:
            registry.async_remove(entity_id)
            removed += 1

    for key in LEGACY_BUTTON_KEYS:
        entity_id = registry.async_get_entity_id("button", DOMAIN, f"{entry.entry_id}_{key}")
        if entity_id:
            registry.async_remove(entity_id)
            removed += 1

    if removed:
        _LOGGER.info("Removed %s legacy benchmark entities", removed)


def _append_history(path: str, entry: dict) -> list[dict]:
    history = read_json(path, [])
    if not isinstance(history, list):
        history = []
    history.append(entry)
    history = history[-MAX_HISTORY_ENTRIES:]
    atomic_write_json(path, history)
    return history


def _export_csv(path: str, history: list[dict]) -> None:
    import csv

    tmp = f"{path}.tmp"
    with open(tmp, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=["timestamp", "profile", "score", "cpu_ops_s", "disk_write_mb_s", "disk_read_mb_s", "template_render_ms", "restart_time_s"],
        )
        writer.writeheader()
        for entry in history:
            results = entry.get("results", {})
            writer.writerow({
                "timestamp": entry.get("timestamp"),
                "profile": entry.get("profile"),
                "score": results.get("benchmark_score"),
                "cpu_ops_s": results.get("cpu_ops_s"),
                "disk_write_mb_s": results.get("disk_write_mb_s"),
                "disk_read_mb_s": results.get("disk_read_mb_s"),
                "template_render_ms": results.get("template_render_ms"),
                "restart_time_s": results.get("restart_time_s"),
            })
    os.replace(tmp, path)


def _load_restart_time(hass: HomeAssistant) -> float | None:
    path = hass.config.path(RESTART_STATE_FILE)
    state = read_json(path, {})
    if not isinstance(state, dict) or state.get("state") != "pending":
        return None
    started_at = state.get("started_at")
    if not isinstance(started_at, int | float):
        return None
    try:
        os.remove(path)
    except OSError:
        pass
    return round(max(time.time() - started_at, 0), 1)


def _refresh_links(hass: HomeAssistant) -> None:
    hass.data[DATA_REPOSITORY_URL] = GITHUB_REPOSITORY_URL
    hass.data[DATA_ISSUE_URL] = GITHUB_ISSUES_URL


async def _notify(hass: HomeAssistant, title: str, message: str) -> None:
    await hass.services.async_call("persistent_notification", "create", {"title": title, "message": message}, blocking=False)


def _update_entities(hass: HomeAssistant) -> None:
    for entity in hass.data.get(DATA_ENTITIES, []):
        entity.async_write_ha_state()


async def _set_progress(hass: HomeAssistant, value: int, message: str = "") -> None:
    hass.data[DATA_PROGRESS] = max(0, min(100, int(value)))
    hass.data[DATA_PROGRESS_MESSAGE] = message
    _update_entities(hass)


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    hass.data.setdefault(DATA_RUNNING, False)
    hass.data.setdefault(DATA_PROGRESS, 0)
    hass.data.setdefault(DATA_PROGRESS_MESSAGE, "Bereit")
    hass.data.setdefault(DATA_LAST_ERROR, None)
    hass.data.setdefault(DATA_ENTITIES, [])
    hass.data[DATA_DASHBOARD_YAML] = build_dashboard_yaml()
    _refresh_links(hass)

    history = await hass.async_add_executor_job(read_json, hass.config.path(DATA_FILE), [])
    hass.data[DATA_LATEST] = history[-1] if isinstance(history, list) and history else None

    async def welcome(_event) -> None:
        meta = await hass.async_add_executor_job(read_json, hass.config.path(META_FILE), {})
        if not isinstance(meta, dict):
            meta = {}
        if not meta.get("welcome_shown_2_1_0"):
            await _notify(hass, "Home Assistant Real World Benchmark", "Willkommen beim Home Assistant Real World Benchmark.")
            meta["welcome_shown_2_1_0"] = True
            await hass.async_add_executor_job(atomic_write_json, hass.config.path(META_FILE), meta)

    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STARTED, welcome)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    hass.data.setdefault(DOMAIN, {})
    hass.data.setdefault(DATA_ENTITIES, [])
    hass.data.setdefault(DATA_RUNNING, False)
    hass.data.setdefault(DATA_PROGRESS, 0)
    hass.data.setdefault(DATA_PROGRESS_MESSAGE, "Bereit")
    hass.data.setdefault(DATA_LAST_ERROR, None)
    _refresh_links(hass)
    _cleanup_legacy_entities(hass, entry)

    registry = device_registry.async_get(hass)
    device = registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, entry.entry_id)},
        name="Benchmark",
        manufacturer="Jarnsen",
        model="Home Assistant Real World Benchmark",
        sw_version=INTEGRATION_VERSION,
    )
    hass.data[DOMAIN]["device"] = device

    async def handle_start(call: ServiceCall) -> None:
        profile = call.data.get("profile", "normal")
        restart = call.data.get("restart", False)
        if profile not in PROFILES:
            raise vol.Invalid(f"Unknown profile: {profile}")
        if hass.data.get(DATA_RUNNING):
            await _notify(hass, "Benchmark", "Es läuft bereits ein Benchmark.")
            return
        if restart:
            await hass.async_add_executor_job(atomic_write_json, hass.config.path(RESTART_STATE_FILE), {"state": "pending", "started_at": time.time(), "profile": profile})
            await _notify(hass, "Benchmark", "Restart-Benchmark vorbereitet. Home Assistant startet jetzt neu.")
            await hass.services.async_call("homeassistant", "restart", {}, blocking=True)
            return
        hass.data[DATA_RUNNING] = True
        hass.data[DATA_LAST_ERROR] = None
        await _set_progress(hass, 1, "Benchmark gestartet")
        try:
            restart_time = await hass.async_add_executor_job(_load_restart_time, hass)
            result = await run_benchmark(hass, profile, restart_time, lambda value, message: _set_progress(hass, value, message))
            history = await hass.async_add_executor_job(_append_history, hass.config.path(DATA_FILE), result)
            hass.data[DATA_LATEST] = result
            await _set_progress(hass, 100, "Benchmark abgeschlossen")
            score = result.get("results", {}).get("benchmark_score")
            if isinstance(score, int) and score < SCORE_WARNING_LIMIT:
                await _notify(hass, "Benchmark Warnung", f"Score {score} liegt unter {SCORE_WARNING_LIMIT}.")
            else:
                await _notify(hass, "Benchmark abgeschlossen", f"Score: {score}")
            _LOGGER.info("Benchmark completed: profile=%s history_entries=%s", profile, len(history))
        except Exception as err:
            hass.data[DATA_LAST_ERROR] = str(err)
            await _set_progress(hass, 0, "Benchmark fehlgeschlagen")
            _LOGGER.exception("Benchmark failed")
            await _notify(hass, "Benchmark fehlgeschlagen", str(err))
        finally:
            _refresh_links(hass)
            hass.data[DATA_RUNNING] = False
            _update_entities(hass)

    async def handle_export(call: ServiceCall) -> None:
        history = await hass.async_add_executor_job(read_json, hass.config.path(DATA_FILE), [])
        if not isinstance(history, list):
            history = []
        json_path = hass.config.path(EXPORT_JSON_FILE)
        csv_path = hass.config.path(EXPORT_CSV_FILE)
        await hass.async_add_executor_job(atomic_write_json, json_path, history)
        await hass.async_add_executor_job(_export_csv, csv_path, history)
        hass.data[DATA_LAST_EXPORT] = {"json": json_path, "csv": csv_path}
        _update_entities(hass)
        await _notify(hass, "Benchmark Export", f"Export erstellt:\nJSON: {json_path}\nCSV: {csv_path}")

    async def handle_export_worldlist(call: ServiceCall) -> None:
        latest = hass.data.get(DATA_LATEST)
        if not latest:
            await _notify(hass, "Worldlist Export", "Es gibt noch kein Benchmark-Ergebnis. Starte zuerst einen Benchmark.")
            return
        payload = _build_worldlist_payload(latest)
        export_path = hass.config.path(WORLDLIST_EXPORT_FILE)
        await hass.async_add_executor_job(atomic_write_json, export_path, payload)
        hass.data[DATA_LAST_WORLDLIST_EXPORT] = export_path
        _update_entities(hass)
        await _notify(hass, "Worldlist Export", f"Anonymer Worldlist-Export erstellt:\n{export_path}")

    async def handle_setup_dashboard(call: ServiceCall) -> None:
        yaml = build_dashboard_yaml()
        hass.data[DATA_DASHBOARD_YAML] = yaml
        _update_entities(hass)
        await _notify(hass, "Benchmark Dashboard YAML", f"```yaml\n{yaml}\n```")

    async def handle_create_issue(call: ServiceCall) -> None:
        _refresh_links(hass)
        _update_entities(hass)
        await _notify(hass, "Benchmark Issue melden", f"GitHub Repository:\n{GITHUB_REPOSITORY_URL}\n\nNeues Issue erstellen:\n{GITHUB_ISSUES_URL}")

    hass.services.async_register(DOMAIN, "start", handle_start, schema=vol.Schema({vol.Optional("profile", default="normal"): vol.In(PROFILES), vol.Optional("restart", default=False): bool}))
    hass.services.async_register(DOMAIN, "export", handle_export)
    hass.services.async_register(DOMAIN, "export_worldlist", handle_export_worldlist)
    hass.services.async_register(DOMAIN, "setup_dashboard", handle_setup_dashboard)
    hass.services.async_register(DOMAIN, "create_issue", handle_create_issue)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        for service in ("start", "export", "export_worldlist", "setup_dashboard", "create_issue"):
            if hass.services.has_service(DOMAIN, service):
                hass.services.async_remove(DOMAIN, service)
        hass.data.pop(DATA_ENTITIES, None)
    return unload_ok

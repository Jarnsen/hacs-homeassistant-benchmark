# custom_components/benchmark/__init__.py

import os
import json
import time

from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers import device_registry
from homeassistant.const import EVENT_HOMEASSISTANT_STARTED

from .const import DOMAIN, DATA_FILE
from .services import (
    run_benchmark_sync,
    run_benchmark_async,
    compute_score,
)

def _append_history(path: str, entry: dict) -> None:
    try:
        data = json.load(open(path))
    except Exception:
        data = []
    data.append(entry)
    with open(path, "w") as fp:
        json.dump(data, fp)

async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    path = hass.config.path(DATA_FILE)
    if not os.path.exists(path):
        with open(path, "w") as fp:
            json.dump([], fp)

    # Start- und Ready-Zeit für Boot-Profil
    hass.data["benchmark_start_time"] = time.time()
    hass.bus.async_listen_once(
        EVENT_HOMEASSISTANT_STARTED,
        lambda e: hass.data.__setitem__("benchmark_ha_ready", time.time()),
    )
    return True

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    dr = device_registry.async_get(hass)
    device = dr.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, entry.entry_id)},
        name="Benchmark",
        manufacturer="Home Assistant",
        model="Benchmark",
    )
    hass.data[f"{DOMAIN}_device"] = device

    async def handle_start(call):
        # Start-Hinweis
        await hass.services.async_call(
            "persistent_notification", "create",
            {"title": "Benchmark", "message": "Benchmark gestartet …"},
            blocking=True,
        )

        # Sync-Teil
        sync = await hass.async_add_executor_job(run_benchmark_sync, hass)
        # Async-Teil
        asyncr = await run_benchmark_async(hass)

        # Score berechnen (ohne Frontend-Render)
        merged = {**sync["results"], **asyncr}
        score_val = compute_score(merged, sync["hardware"])
        merged["benchmark_score"] = score_val

        # History
        entry = {
            "timestamp": sync["timestamp"],
            "hardware":  sync["hardware"],
            "results":   merged,
        }
        await hass.async_add_executor_job(
            _append_history, hass.config.path(DATA_FILE), entry
        )

        # Sensoren aktualisieren
        for ent in hass.data.get(f"{DOMAIN}_entities", []):
            ent.update()
            ent.async_write_ha_state()

        # Fertig-Hinweis
        await hass.services.async_call(
            "persistent_notification", "create",
            {"title": "Benchmark", "message": "Benchmark abgeschlossen!"},
            blocking=True,
        )

        # Neustart HA
        await hass.services.async_call("homeassistant", "restart", {}, blocking=True)

    hass.services.async_register(DOMAIN, "start", handle_start)
    await hass.config_entries.async_forward_entry_setups(entry, ["sensor", "button"])
    return True

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    hass.services.async_remove(DOMAIN, "start")
    await hass.config_entries.async_forward_entry_unload(entry, "sensor")
    await hass.config_entries.async_forward_entry_unload(entry, "button")
    return True

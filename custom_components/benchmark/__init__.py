# custom_components/benchmark/__init__.py

import os
import json
from homeassistant.core import HomeAssistant, callback
from homeassistant.config_entries import ConfigEntry
from .const import DOMAIN, DATA_FILE
from .services import run_benchmark

def _ensure_history_file(path: str) -> None:
    """Stellt synchron sicher, dass die History-Datei existiert."""
    if not os.path.exists(path):
        with open(path, "w") as fp:
            json.dump([], fp)

def _append_history(path: str, result: dict) -> None:
    """Anhängen eines Ergebnisses an die History-Datei."""
    # Datei öffnen und schreiben im Sync-Executor
    data = []
    if os.path.exists(path):
        with open(path, "r") as fp:
            try:
                data = json.load(fp)
            except Exception:
                data = []
    data.append(result)
    with open(path, "w") as fp:
        json.dump(data, fp)

async def async_setup(hass: HomeAssistant, config: dict):
    """Wird nur bei YAML-Konfiguration aufgerufen (hier: nichts zu tun)."""
    return True

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Richtet die Integration ein."""
    history_path = hass.config.path(DATA_FILE)

    # 1) Stelle History-File asynchron sicher
    await hass.async_add_executor_job(_ensure_history_file, history_path)

    # 2) Registriere den benchmark.start-Service
    async def handle_service(call):
        # Benchmark im Sync-Executor laufen lassen
        result = await hass.async_add_executor_job(run_benchmark, hass, entry)
        # Ergebnis in die History schreiben (ebenfalls im Executor)
        await hass.async_add_executor_job(_append_history, history_path, result)
        # Optional: Event feuern oder Log-Eintrag
        hass.bus.async_fire(f"{DOMAIN}_completed", result)

    hass.services.async_register(DOMAIN, "start", handle_service)

    # 3) WebSocket-API registrieren (für dein Panel)
    from . import websocket_api
    websocket_api.async_register(hass)

    return True

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Cleanup bei Deinstallation."""
    # Entferne den Service
    hass.services.async_remove(DOMAIN, "start")
    # Hier ggf. noch weitere Unload-Tasks
    return True

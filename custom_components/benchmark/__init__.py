import os
import json
from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from .const import DOMAIN, DATA_FILE

async def async_setup(hass: HomeAssistant, config: dict):
    return True

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    # History-File anlegen, falls nicht existiert
    history = hass.config.path(DATA_FILE)
    if not os.path.exists(history):
        with open(history, "w") as fp:
            json.dump([], fp)

    # WebSocket-API registrieren
    from . import websocket_api
    websocket_api.async_register(hass)

    # Sensor-Plattform laden
    hass.config_entries.async_setup_platforms(entry, ["sensor"])
    return True

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry):
    await hass.config_entries.async_unload_platforms(entry, ["sensor"])
    return True

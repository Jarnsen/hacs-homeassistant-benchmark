import os
import json
from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from .const import DOMAIN, DATA_FILE

async def async_setup(hass: HomeAssistant, config: dict):
    return True

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    # History-Datei anlegen
    path = hass.config.path(DATA_FILE)
    if not os.path.exists(path):
        with open(path, "w") as f:
            json.dump([], f)

    # WebSocket-API registrieren
    from . import websocket_api
    websocket_api.async_register(hass)

    return True

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry):
    return True

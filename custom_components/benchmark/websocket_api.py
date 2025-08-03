import os
import json
from homeassistant.components import websocket_api
from .services import run_benchmark
from .const import DOMAIN, DATA_FILE

@websocket_api.websocket_command({ "type": f"{DOMAIN}/start" })
@websocket_api.require_admin
def ws_start(hass, connection, msg):
    # Benchmark durchführen
    entry = hass.config_entries.async_entries(DOMAIN)[0]
    result = run_benchmark(hass)

    # In History speichern
    path = hass.config.path(DATA_FILE)
    history = json.load(open(path))
    history.append(result)
    with open(path, "w") as f:
        json.dump(history, f)

    # Ergebnis zurück an UI
    connection.send_message(websocket_api.result_message(msg["id"], result))

@websocket_api.websocket_command({ "type": f"{DOMAIN}/get_history" })
def ws_history(hass, connection, msg):
    path = hass.config.path(DATA_FILE)
    history = json.load(open(path))
    connection.send_message(websocket_api.result_message(msg["id"], history))

def async_register(hass):
    websocket_api.async_register_command(hass, ws_start)
    websocket_api.async_register_command(hass, ws_history)

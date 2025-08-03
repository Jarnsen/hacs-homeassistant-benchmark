import os
import json
from homeassistant.components import websocket_api
from .services import run_benchmark
from .const import DATA_FILE, DOMAIN

@websocket_api.websocket_command({ "type": f"{DOMAIN}/start" })
@websocket_api.require_admin
def ws_start(hass, connection, msg):
    entry = hass.config_entries.async_entries(DOMAIN)[0]
    results = run_benchmark(hass, entry)
    history_file = hass.config.path(DATA_FILE)
    data = json.load(open(history_file))
    data.append(results)
    with open(history_file, "w") as fp:
        json.dump(data, fp)
    connection.send_message(websocket_api.result_message(msg["id"], results))

@websocket_api.websocket_command({ "type": f"{DOMAIN}/get_history" })
def ws_history(hass, connection, msg):
    history = json.load(open(hass.config.path(DATA_FILE)))
    connection.send_message(websocket_api.result_message(msg["id"], history))

@websocket_api.websocket_command({ "type": f"{DOMAIN}/get_settings" })
def ws_get_settings(hass, connection, msg):
    entry = hass.config_entries.async_entries(DOMAIN)[0]
    connection.send_message(websocket_api.result_message(msg["id"], entry.options))

@websocket_api.websocket_command({
    "type": f"{DOMAIN}/update_settings",
    "options": dict
})
@websocket_api.require_admin
def ws_update_settings(hass, connection, msg):
    entry = hass.config_entries.async_entries(DOMAIN)[0]
    hass.config_entries.async_update_entry(entry, options=msg["options"])
    connection.send_message(websocket_api.result_message(msg["id"], entry.options))

def async_register(hass):
    websocket_api.async_register_command(hass, ws_start)
    websocket_api.async_register_command(hass, ws_history)
    websocket_api.async_register_command(hass, ws_get_settings)
    websocket_api.async_register_command(hass, ws_update_settings)

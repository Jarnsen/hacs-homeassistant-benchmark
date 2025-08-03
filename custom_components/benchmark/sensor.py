import json
import logging
from homeassistant.helpers.entity import Entity
from .const import DOMAIN, DATA_FILE

_LOGGER = logging.getLogger(__name__)

async def async_setup_platform(hass, config, add_entities, discovery_info=None):
    path = hass.config.path(DATA_FILE)
    try:
        data = json.load(open(path))
        latest = data[-1]["results"] if data else {}
    except Exception as e:
        _LOGGER.error("Benchmark-History nicht lesbar: %s", e)
        latest = {}

    entities = [BenchmarkSensor(key, path) for key in latest]
    add_entities(entities, True)

class BenchmarkSensor(Entity):
    def __init__(self, key, path):
        self._key = key
        self._path = path
        self._state = None
        self._attrs = {}

    @property
    def name(self):
        return f"benchmark {self._key}"

    @property
    def unique_id(self):
        return f"{DOMAIN}_{self._key}"

    @property
    def state(self):
        return self._state

    @property
    def extra_state_attributes(self):
        return self._attrs

    def update(self):
        try:
            data = json.load(open(self._path))
            last = data[-1]
            self._state = last["results"].get(self._key)
            self._attrs = {
                "timestamp": last.get("timestamp"),
                "ha_version": last.get("ha_version"),
                "hardware": last.get("hardware"),
            }
        except Exception as e:
            _LOGGER.error("Sensor-Update fehlgeschlagen: %s", e)

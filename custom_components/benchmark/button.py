from homeassistant.components.button import ButtonEntity
from .const import DOMAIN

async def async_setup_entry(hass, entry, async_add_entities):
    device = hass.data[f"{DOMAIN}_device"]
    async_add_entities([BenchmarkStartButton(hass, device)], True)

class BenchmarkStartButton(ButtonEntity):
    def __init__(self, hass, device_entry):
        self._hass = hass
        self._device_entry = device_entry
        self._attr_name = "Start Benchmark"
        self._attr_unique_id = "benchmark_start"
        self._attr_should_poll = False

    @property
    def device_info(self):
        return {
            "identifiers": self._device_entry.identifiers,
            "name": self._device_entry.name,
            "manufacturer": self._device_entry.manufacturer,
            "model": self._device_entry.model,
        }

    async def async_press(self):
        await self._hass.services.async_call(DOMAIN, "start", {})

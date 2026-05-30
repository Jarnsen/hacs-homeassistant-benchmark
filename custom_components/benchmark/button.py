from __future__ import annotations

from homeassistant.components.button import ButtonEntity

from .const import ATTRIBUTION, DATA_DEVICE, DOMAIN


async def async_setup_entry(hass, entry, async_add_entities):
    device = hass.data[DATA_DEVICE]
    async_add_entities(
        [
            BenchmarkActionButton(hass, entry.entry_id, device, "start", "Start Benchmark", "mdi:play-speed", "start"),
            BenchmarkActionButton(hass, entry.entry_id, device, "restart", "Restart Benchmark", "mdi:restart", "restart_benchmark"),
        ]
    )


class BenchmarkActionButton(ButtonEntity):
    _attr_has_entity_name = True
    _attr_attribution = ATTRIBUTION
    _attr_should_poll = False

    def __init__(self, hass, entry_id: str, device_entry, key: str, name: str, icon: str, service: str):
        self._hass = hass
        self._device_entry = device_entry
        self._service = service
        self._attr_name = name
        self._attr_icon = icon
        self._attr_unique_id = f"{entry_id}_{key}_button"

    @property
    def device_info(self):
        return {
            "identifiers": self._device_entry.identifiers,
            "name": self._device_entry.name,
            "manufacturer": self._device_entry.manufacturer,
            "model": self._device_entry.model,
        }

    async def async_press(self):
        await self._hass.services.async_call(DOMAIN, self._service, {}, blocking=False)

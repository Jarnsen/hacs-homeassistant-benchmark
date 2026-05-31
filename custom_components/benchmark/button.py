from __future__ import annotations

from homeassistant.components.button import ButtonEntity

from .const import ATTRIBUTION, DOMAIN


async def async_setup_entry(hass, entry, async_add_entities) -> None:
    device = hass.data[DOMAIN]["device"]
    async_add_entities(
        [
            BenchmarkButton(hass, entry.entry_id, device, "start_light", "Start Light", "mdi:play", "light"),
            BenchmarkButton(hass, entry.entry_id, device, "start_normal", "Start Normal", "mdi:play-speed", "normal"),
            BenchmarkButton(hass, entry.entry_id, device, "start_heavy", "Start Heavy", "mdi:rocket-launch", "heavy"),
            BenchmarkRestartButton(hass, entry.entry_id, device),
        ]
    )


class BenchmarkButton(ButtonEntity):
    _attr_has_entity_name = True
    _attr_attribution = ATTRIBUTION
    _attr_should_poll = False

    def __init__(self, hass, entry_id: str, device_entry, key: str, name: str, icon: str, profile: str) -> None:
        self._hass = hass
        self._device_entry = device_entry
        self._profile = profile
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

    async def async_press(self) -> None:
        await self._hass.services.async_call(
            DOMAIN,
            "start",
            {"profile": self._profile, "restart": False},
            blocking=False,
        )


class BenchmarkRestartButton(ButtonEntity):
    _attr_has_entity_name = True
    _attr_attribution = ATTRIBUTION
    _attr_should_poll = False

    def __init__(self, hass, entry_id: str, device_entry) -> None:
        self._hass = hass
        self._device_entry = device_entry
        self._attr_name = "Restart Benchmark"
        self._attr_icon = "mdi:restart"
        self._attr_unique_id = f"{entry_id}_restart_benchmark_button"

    @property
    def device_info(self):
        return {
            "identifiers": self._device_entry.identifiers,
            "name": self._device_entry.name,
            "manufacturer": self._device_entry.manufacturer,
            "model": self._device_entry.model,
        }

    async def async_press(self) -> None:
        await self._hass.services.async_call(
            DOMAIN,
            "start",
            {"profile": "normal", "restart": True},
            blocking=False,
        )

from __future__ import annotations

from homeassistant.components.button import ButtonEntity

from .const import ATTRIBUTION, DOMAIN


async def async_setup_entry(hass, entry, async_add_entities) -> None:
    device = hass.data[DOMAIN]["device"]
    async_add_entities(
        [
            BenchmarkStartButton(hass, entry.entry_id, device),
            BenchmarkWorldlistExportButton(hass, entry.entry_id, device),
            BenchmarkRankingIssueButton(hass, entry.entry_id, device),
            BenchmarkIssueButton(hass, entry.entry_id, device),
        ]
    )


class BenchmarkBaseButton(ButtonEntity):
    _attr_has_entity_name = True
    _attr_attribution = ATTRIBUTION
    _attr_should_poll = False

    def __init__(self, hass, entry_id: str, device_entry, key: str, name: str, icon: str) -> None:
        self._hass = hass
        self._device_entry = device_entry
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


class BenchmarkStartButton(BenchmarkBaseButton):
    def __init__(self, hass, entry_id: str, device_entry) -> None:
        super().__init__(hass, entry_id, device_entry, "start_real_world_benchmark", "Start Real World Benchmark", "mdi:speedometer")

    async def async_press(self) -> None:
        await self._hass.services.async_call(
            DOMAIN,
            "start",
            {"profile": "normal", "restart": False},
            blocking=False,
        )


class BenchmarkWorldlistExportButton(BenchmarkBaseButton):
    def __init__(self, hass, entry_id: str, device_entry) -> None:
        super().__init__(hass, entry_id, device_entry, "export_worldlist", "Export Worldlist", "mdi:earth")

    async def async_press(self) -> None:
        await self._hass.services.async_call(
            DOMAIN,
            "export_worldlist",
            {},
            blocking=False,
        )


class BenchmarkRankingIssueButton(BenchmarkBaseButton):
    def __init__(self, hass, entry_id: str, device_entry) -> None:
        super().__init__(hass, entry_id, device_entry, "create_ranking_issue", "Create Ranking Issue", "mdi:trophy")

    async def async_press(self) -> None:
        await self._hass.services.async_call(
            DOMAIN,
            "create_ranking_issue",
            {},
            blocking=False,
        )


class BenchmarkIssueButton(BenchmarkBaseButton):
    def __init__(self, hass, entry_id: str, device_entry) -> None:
        super().__init__(hass, entry_id, device_entry, "create_issue", "Create Issue", "mdi:github")

    async def async_press(self) -> None:
        await self._hass.services.async_call(
            DOMAIN,
            "create_issue",
            {},
            blocking=False,
        )

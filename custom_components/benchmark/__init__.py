"""Home Assistant Performance Benchmark integration."""

from __future__ import annotations

import logging
from typing import cast

import voluptuous as vol
from homeassistant.config_entries import ConfigEntry, ConfigEntryState
from homeassistant.const import EVENT_HOMEASSISTANT_STARTED, Platform
from homeassistant.core import CoreState, Event, HomeAssistant, ServiceCall, callback
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.typing import ConfigType

from .const import (
    DOMAIN,
    PROFILE_ALIASES,
    PROFILES,
    SERVICE_CREATE_ISSUE,
    SERVICE_CREATE_RANKING_ISSUE,
    SERVICE_EXPORT,
    SERVICE_EXPORT_WORLDLIST,
    SERVICE_RESTART_AND_RUN,
    SERVICE_SETUP_DASHBOARD,
    SERVICE_START,
)
from .runtime import BenchmarkConfigEntry, BenchmarkRuntime
from .storage import async_load_store

_LOGGER = logging.getLogger(__name__)
PLATFORMS: list[Platform] = [Platform.SENSOR, Platform.BUTTON]
CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

PROFILE_VALUES = (*PROFILES, *PROFILE_ALIASES)
START_SCHEMA = vol.Schema(
    {
        vol.Optional("profile"): vol.In(PROFILE_VALUES),
        vol.Optional("restart", default=False): cv.boolean,
    }
)
PROFILE_SCHEMA = vol.Schema(
    {
        vol.Optional("profile"): vol.In(PROFILE_VALUES),
    }
)

REMOVED_V2_SENSOR_KEYS = (
    "cpu_performance",
    "disk_write",
    "disk_read",
    "worldlist_export",
    "ranking_issue",
    "support_issue",
)


def _runtime(hass: HomeAssistant) -> BenchmarkRuntime:
    """Return the single loaded runtime or raise a user-facing error."""
    loaded = [
        entry
        for entry in hass.config_entries.async_entries(DOMAIN)
        if entry.state is ConfigEntryState.LOADED
    ]
    if not loaded:
        raise ServiceValidationError(
            "Home Assistant Performance Benchmark is not loaded"
        )
    return cast(BenchmarkRuntime, loaded[0].runtime_data)


async def async_setup(hass: HomeAssistant, _config: ConfigType) -> bool:
    """Register integration actions independently from config entry setup."""

    async def _handle_start(call: ServiceCall) -> None:
        runtime = _runtime(hass)
        profile = call.data.get("profile")
        if call.data.get("restart", False):
            await runtime.async_prepare_restart(profile)
            return
        await runtime.async_run(profile)

    async def _handle_restart(call: ServiceCall) -> None:
        await _runtime(hass).async_prepare_restart(call.data.get("profile"))

    async def _handle_export(_call: ServiceCall) -> None:
        await _runtime(hass).async_export()

    async def _handle_worldlist(_call: ServiceCall) -> None:
        await _runtime(hass).async_export_worldlist()

    async def _handle_ranking_issue(_call: ServiceCall) -> None:
        await _runtime(hass).async_show_ranking_issue()

    async def _handle_dashboard(_call: ServiceCall) -> None:
        await _runtime(hass).async_show_dashboard()

    async def _handle_issue(_call: ServiceCall) -> None:
        await _runtime(hass).async_show_support_issue()

    hass.services.async_register(
        DOMAIN,
        SERVICE_START,
        _handle_start,
        schema=START_SCHEMA,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_RESTART_AND_RUN,
        _handle_restart,
        schema=PROFILE_SCHEMA,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_EXPORT,
        _handle_export,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_EXPORT_WORLDLIST,
        _handle_worldlist,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_CREATE_RANKING_ISSUE,
        _handle_ranking_issue,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_SETUP_DASHBOARD,
        _handle_dashboard,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_CREATE_ISSUE,
        _handle_issue,
    )
    return True


def _cleanup_removed_v2_entities(
    hass: HomeAssistant,
    entry: ConfigEntry,
) -> None:
    """Remove entity-registry entries that have no v3 equivalent."""
    registry = er.async_get(hass)
    for key in REMOVED_V2_SENSOR_KEYS:
        entity_id = registry.async_get_entity_id(
            Platform.SENSOR,
            DOMAIN,
            f"{entry.entry_id}_{key}",
        )
        if entity_id:
            registry.async_remove(entity_id)


async def _async_options_updated(
    hass: HomeAssistant,
    entry: BenchmarkConfigEntry,
) -> None:
    """Reload after options change."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: BenchmarkConfigEntry,
) -> bool:
    """Set up a benchmark config entry."""
    store, stored = await async_load_store(hass, entry.entry_id)
    runtime = BenchmarkRuntime(hass, entry, store, stored)
    entry.runtime_data = runtime
    entry.async_on_unload(entry.add_update_listener(_async_options_updated))
    _cleanup_removed_v2_entities(hass, entry)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    if runtime.pending_restart:
        if hass.state is CoreState.running:
            hass.async_create_task(
                runtime.async_resume_pending_restart(),
                "resume benchmark after restart",
            )
        else:

            @callback
            def _on_started(_event: Event) -> None:
                hass.async_create_task(
                    runtime.async_resume_pending_restart(),
                    "resume benchmark after restart",
                )

            entry.async_on_unload(
                hass.bus.async_listen_once(
                    EVENT_HOMEASSISTANT_STARTED,
                    _on_started,
                )
            )
    return True


async def async_unload_entry(
    hass: HomeAssistant,
    entry: BenchmarkConfigEntry,
) -> bool:
    """Unload a benchmark config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def async_migrate_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
) -> bool:
    """Migrate the empty v1 config entry to the v3 integration model."""
    if entry.version == 1:
        hass.config_entries.async_update_entry(entry, version=2)
        _LOGGER.info("Migrated benchmark config entry to version 2")
    return True

"""Config and options flows for Home Assistant Performance Benchmark."""

from __future__ import annotations

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import config_validation as cv

from .const import (
    CONF_DEFAULT_PROFILE,
    CONF_NOTIFICATIONS,
    DEFAULT_NOTIFICATIONS,
    DEFAULT_PROFILE,
    DOMAIN,
    NAME,
    PROFILES,
)


class BenchmarkConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle the single benchmark config entry."""

    VERSION = 2

    async def async_step_user(
        self,
        user_input: dict | None = None,
    ) -> FlowResult:
        """Create the integration entry."""
        await self.async_set_unique_id(DOMAIN)
        self._abort_if_unique_id_configured()
        if user_input is None:
            return self.async_show_form(
                step_id="user",
                data_schema=vol.Schema({}),
            )
        return self.async_create_entry(title=NAME, data={})

    @staticmethod
    @callback
    def async_get_options_flow(
        _config_entry: config_entries.ConfigEntry,
    ) -> config_entries.OptionsFlow:
        """Return the options flow."""
        return BenchmarkOptionsFlow()


class BenchmarkOptionsFlow(config_entries.OptionsFlow):
    """Configure default benchmark behavior."""

    async def async_step_init(
        self,
        user_input: dict | None = None,
    ) -> FlowResult:
        """Manage benchmark options."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)
        options = self.config_entry.options
        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_DEFAULT_PROFILE,
                        default=options.get(
                            CONF_DEFAULT_PROFILE,
                            DEFAULT_PROFILE,
                        ),
                    ): vol.In(PROFILES),
                    vol.Required(
                        CONF_NOTIFICATIONS,
                        default=options.get(
                            CONF_NOTIFICATIONS,
                            DEFAULT_NOTIFICATIONS,
                        ),
                    ): cv.boolean,
                }
            ),
        )

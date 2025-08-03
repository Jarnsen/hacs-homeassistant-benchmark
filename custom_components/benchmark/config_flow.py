import voluptuous as vol
from homeassistant import config_entries
from .const import DOMAIN, CONF_SHOW_UUID, DEFAULT_SHOW_UUID

STEP_USER_DATA_SCHEMA = vol.Schema({
    vol.Optional(CONF_SHOW_UUID, default=DEFAULT_SHOW_UUID): bool
})

class BenchmarkConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    async def async_step_user(self, user_input=None):
        if user_input is None:
            return self.async_show_form(
                step_id="user",
                data_schema=STEP_USER_DATA_SCHEMA
            )
        return self.async_create_entry(title="Benchmark", data=user_input)

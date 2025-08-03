import voluptuous as vol
from homeassistant import config_entries
from .const import DOMAIN

STEP_USER_DATA_SCHEMA = vol.Schema({})

class BenchmarkConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    async def async_step_user(self, user_input=None):
        if user_input is None:
            return self.async_show_form(
                step_id="user",
                data_schema=STEP_USER_DATA_SCHEMA
            )
        return self.async_create_entry(title="Benchmark", data={})

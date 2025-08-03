import voluptuous as vol
from homeassistant import config_entries
from .const import CONF_SHOW_UUID, DEFAULT_SHOW_UUID

STEP_OPTIONS_SCHEMA = vol.Schema({
    vol.Optional(CONF_SHOW_UUID, default=DEFAULT_SHOW_UUID): bool
})

class BenchmarkOptionsFlow(config_entries.OptionsFlow):
    def __init__(self, config_entry):
        self.config_entry = config_entry

    async def async_step_init(self, user_input=None):
        if user_input is None:
            return self.async_show_form(
                step_id="init",
                data_schema=STEP_OPTIONS_SCHEMA
            )
        return self.async_create_entry(title="", data=user_input)

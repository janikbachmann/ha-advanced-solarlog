"""Config flow for the Advanced Solar-Log integration."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_PORT
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import AdvancedSolarLogAuthError, AdvancedSolarLogClient, AdvancedSolarLogError
from .const import (
    CONF_EXTENDED_DATA,
    CONF_POLL_INTERVAL,
    DEFAULT_POLL_INTERVAL,
    DEFAULT_PORT,
    DOMAIN,
    MAX_POLL_INTERVAL,
    MIN_POLL_INTERVAL,
)

STEP_USER_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): str,
        vol.Optional(CONF_PORT, default=DEFAULT_PORT): vol.Coerce(int),
        vol.Optional(CONF_PASSWORD, default=""): str,
    }
)


async def _async_validate(hass: HomeAssistant, data: dict[str, Any]) -> bool:
    """Check the host answers, and report whether the protected values are readable.

    Returns True when battery, yearly totals and per-inverter values can be
    fetched. That needs the Solar-Log user password on most firmware.
    """
    client = AdvancedSolarLogClient(
        async_get_clientsession(hass),
        host=data[CONF_HOST],
        port=data.get(CONF_PORT, DEFAULT_PORT),
        password=data.get(CONF_PASSWORD) or None,
    )
    if not await client.async_test_connection():
        raise AdvancedSolarLogError("Host did not answer like a Solar-Log")

    if data.get(CONF_PASSWORD):
        await client.async_login()

    return await client.async_test_extended_data()


class AdvancedSolarLogConfigFlow(ConfigFlow, domain=DOMAIN):
    """Asks for the Solar-Log host and, if set, its password."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """The only setup step."""
        errors: dict[str, str] = {}
        if user_input is not None:
            host = user_input[CONF_HOST].strip()
            user_input[CONF_HOST] = host
            await self.async_set_unique_id(host.lower())
            self._abort_if_unique_id_configured()
            try:
                extended_data = await _async_validate(self.hass, user_input)
            except AdvancedSolarLogAuthError:
                errors["base"] = "invalid_auth"
            except AdvancedSolarLogError:
                errors["base"] = "cannot_connect"
            else:
                if not user_input.get(CONF_PASSWORD):
                    user_input.pop(CONF_PASSWORD, None)
                user_input[CONF_EXTENDED_DATA] = extended_data
                # Short title: it becomes the device name and therefore part of
                # every entity ID. Which device is meant is shown on the device
                # page through its configuration_url.
                return self.async_create_entry(
                    title="Advanced Solar-Log", data=user_input
                )

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_SCHEMA, errors=errors
        )

    async def async_step_reauth(self, entry_data: dict[str, Any]) -> ConfigFlowResult:
        """Triggered when the Solar-Log stops accepting the stored password."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Ask for the device password again."""
        errors: dict[str, str] = {}
        entry = self._get_reauth_entry()
        if user_input is not None:
            data = {**entry.data, CONF_PASSWORD: user_input[CONF_PASSWORD]}
            try:
                data[CONF_EXTENDED_DATA] = await _async_validate(self.hass, data)
            except AdvancedSolarLogAuthError:
                errors["base"] = "invalid_auth"
            except AdvancedSolarLogError:
                errors["base"] = "cannot_connect"
            else:
                return self.async_update_reload_and_abort(entry, data=data)

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema({vol.Required(CONF_PASSWORD): str}),
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        """Options: poll interval and the protected values."""
        return AdvancedSolarLogOptionsFlow()


class AdvancedSolarLogOptionsFlow(OptionsFlow):
    """Lets the poll interval and the extended values be changed later."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """The only options step."""
        if user_input is not None:
            return self.async_create_entry(data=user_input)

        entry = self.config_entry
        schema = vol.Schema(
            {
                vol.Optional(
                    CONF_POLL_INTERVAL,
                    default=entry.options.get(
                        CONF_POLL_INTERVAL, DEFAULT_POLL_INTERVAL
                    ),
                ): vol.All(
                    vol.Coerce(int),
                    vol.Range(min=MIN_POLL_INTERVAL, max=MAX_POLL_INTERVAL),
                ),
                vol.Optional(
                    CONF_EXTENDED_DATA,
                    default=entry.options.get(
                        CONF_EXTENDED_DATA, entry.data.get(CONF_EXTENDED_DATA, False)
                    ),
                ): bool,
            }
        )
        return self.async_show_form(step_id="init", data_schema=schema)

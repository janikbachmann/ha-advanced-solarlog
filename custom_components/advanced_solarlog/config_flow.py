"""Config-Flow fuer die EnergyOptimizer-Integration."""

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
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import AdvancedSolarLogAuthError, AdvancedSolarLogClient, AdvancedSolarLogError
from .const import (
    CONF_POLL_INTERVAL,
    DEFAULT_POLL_INTERVAL,
    DEFAULT_PORT,
    DOMAIN,
    MAX_POLL_INTERVAL,
    MIN_POLL_INTERVAL,
)

STEP_USER_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST, default="energyoptimizer.local"): str,
        vol.Optional(CONF_PORT, default=DEFAULT_PORT): vol.Coerce(int),
        vol.Optional(CONF_PASSWORD, default=""): str,
    }
)


async def _async_validate(hass, data: dict[str, Any]) -> dict[str, Any]:
    """Verbindung pruefen und Geraetenamen ermitteln."""
    client = AdvancedSolarLogClient(
        async_get_clientsession(hass),
        host=data[CONF_HOST],
        port=data.get(CONF_PORT, DEFAULT_PORT),
        password=data.get(CONF_PASSWORD) or None,
    )
    status = await client.async_get_status()
    return status


class AdvancedSolarLogConfigFlow(ConfigFlow, domain=DOMAIN):
    """Fuehrt den Nutzer durch Host/Passwort."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Erster und einziger Einrichtungsschritt."""
        errors: dict[str, str] = {}
        if user_input is not None:
            host = user_input[CONF_HOST].strip()
            user_input[CONF_HOST] = host
            await self.async_set_unique_id(host.lower())
            self._abort_if_unique_id_configured()
            try:
                await _async_validate(self.hass, user_input)
            except AdvancedSolarLogAuthError:
                errors["base"] = "invalid_auth"
            except AdvancedSolarLogError:
                errors["base"] = "cannot_connect"
            else:
                if not user_input.get(CONF_PASSWORD):
                    user_input.pop(CONF_PASSWORD, None)
                # Kurzer Titel: er wird zum Geraetenamen und steckt damit in jeder
                # Entity-ID. Welches Geraet gemeint ist, zeigt die Geraeteseite
                # ueber configuration_url.
                return self.async_create_entry(title="Advanced Solar-Log", data=user_input)

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_SCHEMA, errors=errors
        )

    async def async_step_reauth(
        self, entry_data: dict[str, Any]
    ) -> ConfigFlowResult:
        """Wird ausgeloest, wenn das Geraet 401 liefert."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Nur das Web-Passwort neu abfragen."""
        errors: dict[str, str] = {}
        entry = self._get_reauth_entry()
        if user_input is not None:
            data = {**entry.data, CONF_PASSWORD: user_input[CONF_PASSWORD]}
            try:
                await _async_validate(self.hass, data)
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
        """Optionen (Poll-Intervall)."""
        return AdvancedSolarLogOptionsFlow()


class AdvancedSolarLogOptionsFlow(OptionsFlow):
    """Erlaubt das Anpassen des Poll-Intervalls."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Einziger Optionsschritt."""
        if user_input is not None:
            return self.async_create_entry(data=user_input)

        current = self.config_entry.options.get(
            CONF_POLL_INTERVAL, DEFAULT_POLL_INTERVAL
        )
        schema = vol.Schema(
            {
                vol.Optional(CONF_POLL_INTERVAL, default=current): vol.All(
                    vol.Coerce(int),
                    vol.Range(min=MIN_POLL_INTERVAL, max=MAX_POLL_INTERVAL),
                )
            }
        )
        return self.async_show_form(step_id="init", data_schema=schema)

"""Config flow: name + host + port, validated by reading the screen list."""

from __future__ import annotations

from typing import Any

import voluptuous as vol
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_PORT
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .coex import DEFAULT_PORT, CoexApiError, CoexClient, CoexConnectionError, CoexDeviceLocked
from .const import DEFAULT_NAME, DOMAIN

STEP_USER_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): vol.All(str, vol.Length(min=1)),
        vol.Optional(CONF_PORT, default=DEFAULT_PORT): cv.port,
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): str,
    }
)


class CoexConfigFlow(ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            host = user_input[CONF_HOST].strip().lower()
            port = int(user_input.get(CONF_PORT, DEFAULT_PORT))
            name = (user_input.get(CONF_NAME) or DEFAULT_NAME).strip() or DEFAULT_NAME
            try:
                client = CoexClient(host, port, session=async_get_clientsession(self.hass))
            except ValueError:
                errors["base"] = "invalid_host"
                return self.async_show_form(
                    step_id="user", data_schema=STEP_USER_SCHEMA, errors=errors
                )
            host = client.host
            await self.async_set_unique_id(f"{host}:{port}")
            self._abort_if_unique_id_configured()

            try:
                screens = await client.get_screens()
                if not any(screen.screen_id for screen in screens):
                    errors["base"] = "no_screens"
            except CoexDeviceLocked:
                errors["base"] = "device_locked"
            except CoexConnectionError:
                errors["base"] = "cannot_connect"
            except CoexApiError:
                errors["base"] = "api_error"
            except (ValueError, TypeError, KeyError):
                errors["base"] = "api_error"
            if not errors:
                return self.async_create_entry(
                    title=name, data={CONF_HOST: host, CONF_PORT: port, CONF_NAME: name}
                )

        return self.async_show_form(step_id="user", data_schema=STEP_USER_SCHEMA, errors=errors)

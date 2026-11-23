"""Setting up Cellar Circle: register Home Assistant as a client, then the member signs in on Cellar Circle itself."""

from __future__ import annotations

from collections.abc import Mapping
import logging
from typing import Any, override
from urllib.parse import urlparse

import probatio

from homeassistant.config_entries import SOURCE_REAUTH, ConfigFlowResult
from homeassistant.const import CONF_URL
from homeassistant.helpers import config_entry_oauth2_flow
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import AgentsOff, CannotConnect, CellarCircleError, discover, normalise_url, register_client
from .const import (
    CLIENT_NAME,
    CONF_AUTHORIZE_URL,
    CONF_BASE_URL,
    CONF_CLIENT_ID,
    CONF_TOKEN_URL,
    DEFAULT_URL,
    DOMAIN,
    SCOPE,
)
from .oauth import CellarCircleImplementation


class CellarCircleFlow(config_entry_oauth2_flow.AbstractOAuth2FlowHandler, domain=DOMAIN):
    """Config flow. It replaces the usual "pick credentials" step: the client is registered on the spot."""

    DOMAIN = DOMAIN

    def __init__(self) -> None:
        super().__init__()
        self._base_url = ""
        self._client_id = ""
        self._authorize_url = ""
        self._token_url = ""

    @property
    @override
    def logger(self) -> logging.Logger:
        return logging.getLogger(__name__)

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                self._base_url = normalise_url(user_input[CONF_URL])
                session = async_get_clientsession(self.hass)
                meta = await discover(session, self._base_url)
                redirect_uri = config_entry_oauth2_flow.async_get_redirect_uri(self.hass)
                self._client_id = await register_client(session, meta, name=CLIENT_NAME, redirect_uri=redirect_uri, scope=SCOPE)
            except AgentsOff:
                errors["base"] = "api_off"
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except CellarCircleError:
                errors["base"] = "registration_failed"
            else:
                await self.async_set_unique_id(urlparse(self._base_url).netloc)
                self._abort_if_unique_id_configured()
                self._authorize_url = meta["authorization_endpoint"]
                self._token_url = meta["token_endpoint"]
                return await self._start_sign_in()

        return self.async_show_form(
            step_id="user",
            data_schema=probatio.Schema({probatio.Required(CONF_URL, default=DEFAULT_URL): str}),
            errors=errors,
        )

    async def async_step_reauth(self, entry_data: Mapping[str, Any]) -> ConfigFlowResult:
        """The token was refused: sign in again, as the same client."""
        entry = self._get_reauth_entry()
        self._base_url = entry.data[CONF_BASE_URL]
        self._client_id = entry.data[CONF_CLIENT_ID]
        self._authorize_url = entry.data[CONF_AUTHORIZE_URL]
        self._token_url = entry.data[CONF_TOKEN_URL]
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        if user_input is None:
            return self.async_show_form(step_id="reauth_confirm")
        return await self._start_sign_in()

    async def _start_sign_in(self) -> ConfigFlowResult:
        self.flow_impl = CellarCircleImplementation(
            self.hass,
            base_url=self._base_url,
            client_id=self._client_id,
            authorize_url=self._authorize_url,
            token_url=self._token_url,
        )
        return await self.async_step_auth()

    async def async_oauth_create_entry(self, data: dict) -> ConfigFlowResult:
        data = {
            **data,
            CONF_BASE_URL: self._base_url,
            CONF_CLIENT_ID: self._client_id,
            CONF_AUTHORIZE_URL: self._authorize_url,
            CONF_TOKEN_URL: self._token_url,
        }
        if self.source == SOURCE_REAUTH:
            return self.async_update_reload_and_abort(self._get_reauth_entry(), data=data)
        return self.async_create_entry(title=f"Cellar Circle ({urlparse(self._base_url).netloc})", data=data)

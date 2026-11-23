"""Home Assistant's OAuth2 helper, set up for a client that registered itself (no secret, PKCE, tokens tied to the MCP address)."""

from __future__ import annotations

from typing import override

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import OAuth2TokenRequestConnectionError
from homeassistant.helpers.config_entry_oauth2_flow import LocalOAuth2ImplementationWithPkce

from .const import SCOPE


class CellarCircleImplementation(LocalOAuth2ImplementationWithPkce):
    """One registered client. Its `domain` is the client id, so each connection has its own implementation."""

    def __init__(self, hass: HomeAssistant, *, base_url: str, client_id: str, authorize_url: str, token_url: str) -> None:
        super().__init__(hass, client_id, client_id, authorize_url, token_url)
        self._resource = f"{base_url}/api/mcp"

    @property
    @override
    def name(self) -> str:
        return "Cellar Circle"

    @property
    @override
    def extra_authorize_data(self) -> dict:
        # The member picks what to allow on Cellar Circle's own screen; we ask only to look.
        return {**super().extra_authorize_data, "scope": SCOPE, "resource": self._resource, "prompt": "consent"}

    @property
    @override
    def extra_token_resolve_data(self) -> dict:
        return {**super().extra_token_resolve_data, "resource": self._resource}

    @override
    async def _async_refresh_token(self, token: dict) -> dict:
        # Same as the base class, plus `resource`: without it the new token may not be made for the MCP address.
        # Cellar Circle hands out a new refresh token each time, so the merge below keeps the new one.
        new_token = await self._token_request(
            {"grant_type": "refresh_token", "client_id": self.client_id, "refresh_token": token["refresh_token"], "resource": self._resource}
        )
        if not new_token.get("access_token"):
            raise OAuth2TokenRequestConnectionError(domain=self.service_domain)
        return {**token, **new_token}

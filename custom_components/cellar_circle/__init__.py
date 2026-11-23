"""Cellar Circle: see what is waiting on you, who you owe wine to and who owes you, from Home Assistant."""

from __future__ import annotations

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_entry_oauth2_flow
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import CellarCircleApi
from .const import CONF_AUTHORIZE_URL, CONF_BASE_URL, CONF_CLIENT_ID, CONF_TOKEN_URL
from .coordinator import CellarCircleConfigEntry, CellarCircleCoordinator, token_getter
from .oauth import CellarCircleImplementation

PLATFORMS = [Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: CellarCircleConfigEntry) -> bool:
    # The client registered itself when this was set up, so its details live on the entry, not in application credentials.
    implementation = CellarCircleImplementation(
        hass,
        base_url=entry.data[CONF_BASE_URL],
        client_id=entry.data[CONF_CLIENT_ID],
        authorize_url=entry.data[CONF_AUTHORIZE_URL],
        token_url=entry.data[CONF_TOKEN_URL],
    )
    session = config_entry_oauth2_flow.OAuth2Session(hass, entry, implementation)
    api = CellarCircleApi(async_get_clientsession(hass), entry.data[CONF_BASE_URL], token_getter(session))

    coordinator = CellarCircleCoordinator(hass, entry, api)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: CellarCircleConfigEntry) -> bool:
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

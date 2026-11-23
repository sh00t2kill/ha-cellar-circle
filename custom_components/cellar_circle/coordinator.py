"""Fetches Cellar Circle's numbers every few minutes."""

from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, OAuth2TokenRequestReauthError
from homeassistant.helpers import config_entry_oauth2_flow
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import AgentsOff, AuthError, CellarCircleApi, CellarCircleError
from .const import DOMAIN, UPDATE_INTERVAL
from .parse import Summary, summarise

_LOGGER = logging.getLogger(__name__)

type CellarCircleConfigEntry = ConfigEntry[CellarCircleCoordinator]


class CellarCircleCoordinator(DataUpdateCoordinator[Summary]):
    """Five read-only calls per refresh: what is waiting on me, who I owe and who owes me, and how many offers and swaps are open."""

    config_entry: CellarCircleConfigEntry

    def __init__(self, hass: HomeAssistant, entry: CellarCircleConfigEntry, api: CellarCircleApi) -> None:
        super().__init__(hass, _LOGGER, config_entry=entry, name=DOMAIN, update_interval=UPDATE_INTERVAL)
        self.api = api

    async def _async_update_data(self) -> Summary:
        try:
            open_items = await self.api.call_tool("list_my_open_items")
            people = await self.api.call_tool("list_people")
            # Only the count is wanted, so one page is enough.
            offers = await self.api.call_tool("list_offers")
            swaps = await self.api.call_tool("list_swap_listings")
            # Open listings the member listed or has proposed on.
            my_swaps = await self.api.call_tool("list_swap_listings", {"mineOnly": True})
        except (AuthError, OAuth2TokenRequestReauthError) as err:
            raise ConfigEntryAuthFailed("Cellar Circle no longer accepts this connection") from err
        except AgentsOff as err:
            raise UpdateFailed("Cellar Circle has its API switched off") from err
        except CellarCircleError as err:
            raise UpdateFailed(str(err)) from err
        return summarise(open_items, people, offers, swaps, my_swaps)


def token_getter(session: config_entry_oauth2_flow.OAuth2Session):
    """A function that gives the API a token that is valid right now."""

    async def get() -> str:
        await session.async_ensure_token_valid()
        return str(session.token["access_token"])

    return get

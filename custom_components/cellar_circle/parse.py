"""Turns Cellar Circle's tool replies into the numbers the sensors show. No Home Assistant imports, so it is easy to test."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

OWES_ME = "they owe me"


@dataclass
class Summary:
    """Everything the sensors read, from one refresh."""

    open_items_total: int = 0
    open_items: list[dict[str, str]] = field(default_factory=list)
    open_offers_total: int = 0
    open_swaps_total: int = 0
    my_swaps_total: int = 0
    open_swaps: list[dict[str, str]] = field(default_factory=list)
    my_swaps: list[dict[str, str]] = field(default_factory=list)
    bottles_i_owe: int = 0
    bottles_owed_to_me: int = 0
    money_owed_to_me_cents: int = 0
    money_i_owe_cents: int = 0
    currency: str = "AUD"
    # One row per person, for the sensors' attributes.
    people: list[dict[str, Any]] = field(default_factory=list)


def _swaps(reply: dict[str, Any]) -> list[dict[str, str]]:
    return [
        {"wine": str(s.get("wine", "")), "producer": str(s.get("producer", "")), "wants": str(s.get("lookingFor") or ""), "url": str(s.get("url", ""))}
        for s in reply.get("listings", [])
    ]


def summarise(
    open_items: dict[str, Any],
    people: dict[str, Any],
    offers: dict[str, Any],
    swaps: dict[str, Any] | None = None,
    my_swaps: dict[str, Any] | None = None,
) -> Summary:
    """Builds a Summary from the replies of list_my_open_items, list_people, list_offers and list_swap_listings (all, then mineOnly)."""
    swaps, my_swaps = swaps or {}, my_swaps or {}
    summary = Summary(
        open_items_total=int(open_items.get("total", 0)),
        open_items=[
            {"what": str(i.get("what", "")), "community": str(i.get("community", "")), "url": str(i.get("url", ""))}
            for i in open_items.get("items", [])
        ],
        open_offers_total=int(offers.get("total", 0)),
        open_swaps_total=int(swaps.get("total", 0)),
        my_swaps_total=int(my_swaps.get("total", 0)),
        open_swaps=_swaps(swaps),
        my_swaps=_swaps(my_swaps),
    )
    for person in people.get("people", []):
        owe = int((person.get("iOweThemWine") or {}).get("bottles", 0))
        owed = int((person.get("theyOweMeWine") or {}).get("bottles", 0))
        summary.bottles_i_owe += owe
        summary.bottles_owed_to_me += owed

        money = person.get("money")
        money_text = None
        if money:
            net = money.get("net") or {}
            cents = int(net.get("cents", 0))
            summary.currency = str(net.get("currency") or summary.currency)
            if money.get("direction") == OWES_ME:
                summary.money_owed_to_me_cents += cents
            else:
                summary.money_i_owe_cents += cents
            money_text = f"{money.get('direction')} {net.get('display', cents / 100)}"

        summary.people.append(
            {
                "name": person.get("name", "Former member"),
                "bottles_i_owe": owe,
                "bottles_owed_to_me": owed,
                "money": money_text,
            }
        )
    return summary

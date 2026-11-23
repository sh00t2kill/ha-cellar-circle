# ha-cellar-circle

A Home Assistant custom integration for [Cellar Circle](../cellar-circle). Kept in its own repo so it has its own releases (HACS).

It uses Cellar Circle's existing API (the MCP endpoint at `<site>/api/mcp`) as a plain JSON-RPC HTTP API. **No AI agent or LLM is involved.** It only reads.

## Sensors (one device, "Cellar Circle")

| Sensor | From | Notes |
|---|---|---|
| Waiting on me | `list_my_open_items` | Count; the items (text, community, link) are in the attributes |
| Bottles I owe / Bottles owed to me | `list_people` | Counts; who and how many are in the attributes |
| Money I owe / Money owed to me | `list_people` | Net across people, in the site's currency |
| Open offers | `list_offers` | Count of offers still taking requests |
| Open swap listings | `list_swap_listings` | Count of listings open to proposals in your communities; the wine, producer and what they want are in the attributes |
| My swaps | `list_swap_listings` (`mineOnly`) | Open listings you listed or have proposed on (the app does not separate the two) |

Refreshed every 10 minutes (five calls; the app allows 120 reads a minute per member).

Attributes include other members' names (who you owe wine to). They are stored in your Home Assistant history like any attribute; exclude them in the recorder if that matters to you.

## How sign-in works

Cellar Circle has no API keys. Setup registers Home Assistant as an OAuth client on the spot (RFC 7591), with the `my.home-assistant.io` redirect, then sends you to Cellar Circle to sign in and choose **Read only**. Tokens last an hour and renew themselves (a new refresh token each time, saved by Home Assistant). If Cellar Circle stops accepting the connection (you disconnect it in the app, or 90 days pass with no use), Home Assistant asks you to sign in again.

## Install (for now, by hand)

Copy `custom_components/cellar_circle` into your Home Assistant's `config/custom_components/`, restart, then Settings → Devices & services → Add integration → Cellar Circle. The site must have `MCP_ENABLED=on`, and your Home Assistant needs My Home Assistant (part of `default_config`) or an https external URL.

## Development

```
pip install pytest pytest-asyncio aiohttp
python -m pytest
```

The tests cover `parse.py` and `api.py`, which import nothing from Home Assistant. The config flow, OAuth class, coordinator and sensors are checked against Home Assistant 2026.11.2's source but have **not** been run inside Home Assistant yet.

`spike/spike.py` is the original proof that the sign-in works (`python spike/spike.py https://<site>`).

## Not done yet

Write services (request bottles, mark collected), payment actions, HACS packaging and a release process, tests that run inside Home Assistant (`pytest-homeassistant-custom-component`, needs Python 3.14), and the repository URLs in `manifest.json`.

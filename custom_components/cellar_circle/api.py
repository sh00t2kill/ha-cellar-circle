"""Plain HTTP calls to Cellar Circle: sign-in discovery, client registration, and the tools over JSON-RPC.

No Home Assistant imports, so the spike and the tests can use it too. Nothing here talks to an AI agent: the MCP endpoint
is used as an ordinary JSON-RPC API.
"""

from __future__ import annotations

from typing import Any
from urllib.parse import urlparse

import aiohttp

TIMEOUT = aiohttp.ClientTimeout(total=20)


class CellarCircleError(Exception):
    """Something went wrong talking to Cellar Circle."""


class CannotConnect(CellarCircleError):
    """The site could not be reached, or did not answer as Cellar Circle does."""


class AgentsOff(CellarCircleError):
    """The site is Cellar Circle but has the API switched off (MCP_ENABLED)."""


class RegistrationFailed(CellarCircleError):
    """The site refused to register Home Assistant."""


class AuthError(CellarCircleError):
    """The token was refused: the member disconnected Home Assistant, or it was not used for too long."""


def normalise_url(url: str) -> str:
    """https://site/ -> https://site (a missing scheme is taken as https)."""
    url = url.strip().rstrip("/")
    if "://" not in url:
        url = f"https://{url}"
    parsed = urlparse(url)
    if not parsed.netloc:
        raise CannotConnect(f"Not a web address: {url}")
    return f"{parsed.scheme}://{parsed.netloc}"


async def discover(session: aiohttp.ClientSession, base_url: str) -> dict[str, Any]:
    """Finds the sign-in server's addresses (RFC 9728, then RFC 8414)."""
    mcp_path = "/api/mcp"
    try:
        async with session.get(f"{base_url}/.well-known/oauth-protected-resource{mcp_path}", timeout=TIMEOUT) as resp:
            if resp.status == 404:
                raise AgentsOff(base_url)
            resp.raise_for_status()
            resource = await resp.json(content_type=None)
        issuer = resource["authorization_servers"][0]
        async with session.get(f"{base_url}/.well-known/oauth-authorization-server{urlparse(issuer).path}", timeout=TIMEOUT) as resp:
            resp.raise_for_status()
            meta = await resp.json(content_type=None)
        for key in ("registration_endpoint", "authorization_endpoint", "token_endpoint"):
            if key not in meta:
                raise CannotConnect(f"Missing {key}")
    except (aiohttp.ClientError, TimeoutError, KeyError, IndexError, ValueError) as err:
        raise CannotConnect(str(err)) from err
    return meta


async def register_client(session: aiohttp.ClientSession, meta: dict[str, Any], *, name: str, redirect_uri: str, scope: str) -> str:
    """Registers Home Assistant as a client (RFC 7591) and returns its client id. There is no secret: it is a public client using PKCE."""
    body = {
        "client_name": name,
        "application_type": "web",
        "redirect_uris": [redirect_uri],
        "token_endpoint_auth_method": "none",
        "grant_types": ["authorization_code", "refresh_token"],
        "response_types": ["code"],
        "scope": scope,
    }
    try:
        async with session.post(meta["registration_endpoint"], json=body, timeout=TIMEOUT) as resp:
            if resp.status != 201:
                raise RegistrationFailed(f"{resp.status}: {(await resp.text())[:200]}")
            return str((await resp.json(content_type=None))["client_id"])
    except (aiohttp.ClientError, TimeoutError, KeyError, ValueError) as err:
        raise RegistrationFailed(str(err)) from err


class CellarCircleApi:
    """Calls Cellar Circle's tools. `get_token` returns a valid access token (refreshing it when needed)."""

    def __init__(self, session: aiohttp.ClientSession, base_url: str, get_token) -> None:
        self._session = session
        self._url = f"{base_url}/api/mcp"
        self._get_token = get_token
        self._next_id = 0

    async def call_tool(self, name: str, arguments: dict[str, Any] | None = None) -> dict[str, Any]:
        """Runs one tool and returns its structured reply."""
        self._next_id += 1
        token = await self._get_token()
        payload = {"jsonrpc": "2.0", "id": self._next_id, "method": "tools/call", "params": {"name": name, "arguments": arguments or {}}}
        headers = {"content-type": "application/json", "accept": "application/json, text/event-stream", "authorization": f"Bearer {token}"}
        try:
            async with self._session.post(self._url, json=payload, headers=headers, timeout=TIMEOUT) as resp:
                if resp.status == 401:
                    raise AuthError(await resp.text())
                if resp.status == 404:
                    raise AgentsOff(self._url)
                if resp.status >= 400:
                    # 403 is a member who cannot use the app right now (terms, removed) or has not given this permission.
                    raise CellarCircleError(f"{resp.status}: {(await resp.text())[:200]}")
                body = await resp.json(content_type=None)
        except (aiohttp.ClientError, TimeoutError) as err:
            raise CannotConnect(str(err)) from err

        if "error" in body:
            raise CellarCircleError(str(body["error"].get("message", body["error"])))
        result = body.get("result", {})
        if result.get("isError"):
            text = " ".join(c.get("text", "") for c in result.get("content", []))
            raise CellarCircleError(text or f"{name} failed")
        return result.get("structuredContent") or {}

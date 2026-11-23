import json

import aiohttp
import pytest
from aiohttp import web
from aiohttp.test_utils import TestServer

from conftest import load

api = load("api")


def make_app(calls):
    app = web.Application()

    async def resource(request):
        return web.json_response({"authorization_servers": [f"{request.scheme}://{request.host}/api/auth"]})

    async def meta(request):
        base = f"{request.scheme}://{request.host}/api/auth/oauth2"
        return web.json_response({"registration_endpoint": f"{base}/register", "authorization_endpoint": f"{base}/authorize", "token_endpoint": f"{base}/token"})

    async def register(request):
        calls.append(await request.json())
        return web.json_response({"client_id": "abc"}, status=201)

    async def mcp(request):
        if request.headers.get("authorization") != "Bearer good":
            return web.Response(status=401, text="no")
        body = await request.json()
        name = body["params"]["name"]
        if name == "boom":
            return web.json_response({"jsonrpc": "2.0", "id": body["id"], "result": {"isError": True, "content": [{"type": "text", "text": "Too many calls"}]}})
        return web.json_response({"jsonrpc": "2.0", "id": body["id"], "result": {"structuredContent": {"total": 1}, "content": []}})

    app.router.add_get("/.well-known/oauth-protected-resource/api/mcp", resource)
    app.router.add_get("/.well-known/oauth-authorization-server/api/auth", meta)
    app.router.add_post("/api/auth/oauth2/register", register)
    app.router.add_post("/api/mcp", mcp)
    return app


@pytest.mark.asyncio
async def test_discover_register_and_call():
    calls = []
    async with TestServer(make_app(calls)) as server:
        base = str(server.make_url("")).rstrip("/")
        async with aiohttp.ClientSession() as session:
            meta = await api.discover(session, base)
            client_id = await api.register_client(session, meta, name="Home Assistant", redirect_uri="https://my.home-assistant.io/redirect/oauth", scope="cellar:read offline_access")
            assert client_id == "abc"
            assert calls[0]["token_endpoint_auth_method"] == "none" and calls[0]["application_type"] == "web"

            async def token():
                return "good"

            client = api.CellarCircleApi(session, base, token)
            assert await client.call_tool("list_offers") == {"total": 1}
            with pytest.raises(api.CellarCircleError, match="Too many calls"):
                await client.call_tool("boom")

            async def bad():
                return "bad"

            with pytest.raises(api.AuthError):
                await api.CellarCircleApi(session, base, bad).call_tool("list_offers")


@pytest.mark.asyncio
async def test_api_switched_off():
    app = web.Application()  # nothing served: every address is a 404
    async with TestServer(app) as server:
        async with aiohttp.ClientSession() as session:
            with pytest.raises(api.AgentsOff):
                await api.discover(session, str(server.make_url("")).rstrip("/"))


def test_normalise_url():
    assert api.normalise_url("cellarcircle.app/") == "https://cellarcircle.app"
    assert api.normalise_url(" https://x.y/some/path ") == "https://x.y"

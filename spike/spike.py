"""Spike: can a Home Assistant integration talk to Cellar Circle's API without any AI agent?

Plays exactly what the integration's config flow would do, with plain HTTP:
  1. discover the OAuth server        (RFC 9728 / RFC 8414)
  2. register itself                  (RFC 7591 dynamic client registration), redirect = my.home-assistant.io
  3. build the authorize URL          (PKCE S256, resource = the MCP endpoint)
  4. exchange the code for tokens     (you paste the redirect URL back)
  5. call MCP tools over JSON-RPC     (initialize, tools/list, list_my_open_items, list_people)
  6. refresh the access token         (what HA does every hour)

Only needs `requests`. Usage:
    python spike.py https://your-cellar-circle-site
Reads/writes .spike-state.json (git-ignored) so steps 5-6 can be re-run without signing in again.
"""

from __future__ import annotations

import base64
import hashlib
import json
import secrets
import sys
from pathlib import Path
from urllib.parse import parse_qs, urlencode, urlparse

import requests

# The redirect Home Assistant's OAuth2 helper uses. It is https, so Cellar Circle accepts it for a "web" client.
REDIRECT_URI = "https://my.home-assistant.io/redirect/oauth"
SCOPE = "cellar:read offline_access"
STATE_FILE = Path(__file__).with_name(".spike-state.json")
TIMEOUT = 20


def b64url(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()


def step(n: int, title: str) -> None:
    print(f"\n--- {n}. {title}")


def load_state() -> dict:
    return json.loads(STATE_FILE.read_text()) if STATE_FILE.exists() else {}


def save_state(state: dict) -> None:
    STATE_FILE.write_text(json.dumps(state, indent=2))


def discover(base: str, mcp_url: str) -> dict:
    step(1, "Discovery")
    path = urlparse(mcp_url).path
    prm = requests.get(f"{base}/.well-known/oauth-protected-resource{path}", timeout=TIMEOUT)
    print("protected-resource:", prm.status_code, prm.text[:300])
    prm.raise_for_status()
    issuer = prm.json()["authorization_servers"][0]
    meta_url = f"{base}/.well-known/oauth-authorization-server{urlparse(issuer).path}"
    meta = requests.get(meta_url, timeout=TIMEOUT)
    print("auth-server metadata:", meta.status_code)
    meta.raise_for_status()
    m = meta.json()
    for key in ("registration_endpoint", "authorization_endpoint", "token_endpoint", "code_challenge_methods_supported", "scopes_supported"):
        print(f"  {key}: {m.get(key)}")
    return m


def register(meta: dict) -> str:
    step(2, "Dynamic client registration")
    res = requests.post(
        meta["registration_endpoint"],
        json={
            "client_name": "Home Assistant (spike)",
            "application_type": "web",
            "redirect_uris": [REDIRECT_URI],
            "token_endpoint_auth_method": "none",
            "grant_types": ["authorization_code", "refresh_token"],
            "response_types": ["code"],
            "scope": SCOPE,
        },
        timeout=TIMEOUT,
    )
    print("status:", res.status_code, res.text[:300])
    res.raise_for_status()
    return res.json()["client_id"]


def authorize_url(meta: dict, client_id: str, mcp_url: str) -> tuple[str, str, str]:
    verifier = b64url(secrets.token_bytes(32))
    state = b64url(secrets.token_bytes(8))
    query = {
        "client_id": client_id,
        "redirect_uri": REDIRECT_URI,
        "response_type": "code",
        "scope": SCOPE,
        "state": state,
        "code_challenge": b64url(hashlib.sha256(verifier.encode()).digest()),
        "code_challenge_method": "S256",
        "resource": mcp_url,
        "prompt": "consent",
    }
    return f"{meta['authorization_endpoint']}?{urlencode(query)}", verifier, state


def exchange(meta: dict, client_id: str, verifier: str, code: str, mcp_url: str) -> dict:
    step(4, "Exchange the code for tokens")
    res = requests.post(
        meta["token_endpoint"],
        data={"grant_type": "authorization_code", "code": code, "redirect_uri": REDIRECT_URI, "client_id": client_id, "code_verifier": verifier, "resource": mcp_url},
        timeout=TIMEOUT,
    )
    print("status:", res.status_code)
    body = res.json()
    print("keys:", sorted(body), "| expires_in:", body.get("expires_in"), "| scope:", body.get("scope"))
    res.raise_for_status()
    return body


def refresh(meta: dict, client_id: str, refresh_token: str, mcp_url: str) -> dict:
    step(6, "Refresh the access token")
    res = requests.post(
        meta["token_endpoint"],
        data={"grant_type": "refresh_token", "refresh_token": refresh_token, "client_id": client_id, "resource": mcp_url},
        timeout=TIMEOUT,
    )
    print("status:", res.status_code)
    body = res.json()
    print("keys:", sorted(body), "| expires_in:", body.get("expires_in"), "| new refresh token issued:", "refresh_token" in body)
    res.raise_for_status()
    return body


def rpc(mcp_url: str, token: str, method: str, params: dict | None = None, rid: int = 1) -> dict:
    res = requests.post(
        mcp_url,
        headers={"content-type": "application/json", "accept": "application/json, text/event-stream", "authorization": f"Bearer {token}"},
        json={"jsonrpc": "2.0", "id": rid, "method": method, **({"params": params} if params else {})},
        timeout=TIMEOUT,
    )
    if res.status_code != 200:
        print(f"  HTTP {res.status_code}: {res.text[:300]} | www-authenticate: {res.headers.get('www-authenticate')}")
        res.raise_for_status()
    return res.json()


def call_tools(mcp_url: str, token: str) -> None:
    step(5, "Call the API (MCP over plain JSON-RPC)")
    init = rpc(mcp_url, token, "initialize", {"protocolVersion": "2025-03-26", "capabilities": {}, "clientInfo": {"name": "ha-cellar-circle-spike", "version": "0"}})
    print("initialize ->", init.get("result", init).get("serverInfo"))
    tools = rpc(mcp_url, token, "tools/list", rid=2)["result"]["tools"]
    print("tools:", ", ".join(t["name"] for t in tools))
    for i, name in enumerate(("list_communities", "list_my_open_items", "list_people"), start=3):
        out = rpc(mcp_url, token, "tools/call", {"name": name, "arguments": {}}, rid=i)["result"]
        print(f"\n{name}: isError={out.get('isError', False)}")
        print("  structuredContent:", json.dumps(out.get("structuredContent"), indent=2)[:1200])


def main() -> None:
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    base = sys.argv[1].rstrip("/")
    mcp_url = f"{base}/api/mcp"
    state = load_state()

    meta = discover(base, mcp_url)

    if "refresh_token" not in state:
        client_id = register(meta)
        step(3, "Sign in")
        url, verifier, expected_state = authorize_url(meta, client_id, mcp_url)
        print("Open this in a browser, sign in, choose 'Read only', and allow:\n\n" + url)
        print("\nYou will land on a my.home-assistant.io page (it will not work; that is fine).")
        pasted = input("Paste the full address from the browser's address bar here: ").strip()
        q = parse_qs(urlparse(pasted).query)
        if q.get("state", [""])[0] != expected_state:
            sys.exit("State did not match.")
        if "code" not in q:
            sys.exit(f"No code in the address: {q}")
        tokens = exchange(meta, client_id, verifier, q["code"][0], mcp_url)
        state = {"client_id": client_id, "access_token": tokens["access_token"], "refresh_token": tokens.get("refresh_token")}
        save_state(state)

    call_tools(mcp_url, state["access_token"])

    if state.get("refresh_token"):
        new = refresh(meta, state["client_id"], state["refresh_token"], mcp_url)
        state["access_token"] = new["access_token"]
        state["refresh_token"] = new.get("refresh_token", state["refresh_token"])
        save_state(state)
        print("\nCalling again with the refreshed token:")
        call_tools(mcp_url, state["access_token"])

    print("\nSpike finished. Delete .spike-state.json to start from a fresh sign-in.")


if __name__ == "__main__":
    main()

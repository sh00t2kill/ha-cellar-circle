"""Constants for the Cellar Circle integration."""

from datetime import timedelta

DOMAIN = "cellar_circle"

DEFAULT_URL = "https://cellarcircle.app"

# Stored on the config entry next to the OAuth token.
CONF_BASE_URL = "base_url"
CONF_CLIENT_ID = "client_id"
CONF_AUTHORIZE_URL = "authorize_url"
CONF_TOKEN_URL = "token_url"

# Read only: the integration looks, it never changes anything. "offline_access" is what lets the token renew.
SCOPE = "cellar:read offline_access"
CLIENT_NAME = "Home Assistant"

UPDATE_INTERVAL = timedelta(minutes=10)
# The app limits a member to 120 looks a minute, shared with any other agent, so each refresh stays at a few calls.
MAX_ITEMS_IN_ATTRIBUTES = 20

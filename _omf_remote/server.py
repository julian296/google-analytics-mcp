"""Remote-Einstiegspunkt für den offiziellen Google-Analytics-MCP-Server.

Ergänzt googleanalytics/google-analytics-mcp um Streamable HTTP und eine
Google-Anmeldung pro Person (FastMCP OAuth-Proxy) – nach demselben Muster wie
der offizielle Google-Ads-MCP-Server.

Diese Datei verändert keine Upstream-Datei. Sie
  1. übernimmt alle Tools, die upstream in analytics_mcp.coordinator.tools
     registriert sind (neue Tools kommen bei Updates automatisch mit), und
  2. ersetzt die Credential-Funktion von upstream, sodass jede API-Abfrage mit
     dem Google-Token der gerade angemeldeten Person läuft – nie mit einem
     Server-Konto.

Read-only: angefordert wird nur der Scope analytics.readonly.
"""

import logging
import os
import pathlib
import sys

from fastmcp import FastMCP
from fastmcp.server.auth.providers.google import GoogleProvider
from fastmcp.server.dependencies import get_access_token
from google.oauth2.credentials import Credentials

import analytics_mcp.tools.client as ga_client
from analytics_mcp import coordinator

logger = logging.getLogger("omf_remote")
logging.basicConfig(level=logging.INFO, stream=sys.stderr)

ANALYTICS_SCOPE = "https://www.googleapis.com/auth/analytics.readonly"


def _env(name: str, default: str | None = None, required: bool = False) -> str | None:
    value = os.environ.get(name, default)
    if required and not value:
        raise SystemExit(f"Umgebungsvariable {name} fehlt.")
    return value


# --- 1. Sicherheitsprüfung gegen Upstream-Änderungen -------------------------
# Wenn Google die Stelle umbaut, an der die Anmeldung entsteht, soll der Server
# nicht starten, statt stillschweigend auf eine andere Anmeldung auszuweichen.
if not callable(getattr(ga_client, "_get_credentials", None)):
    raise SystemExit(
        "Upstream hat analytics_mcp.tools.client._get_credentials entfernt oder "
        "umbenannt – _omf_remote/server.py muss angepasst werden."
    )
if not getattr(coordinator, "tools", None) or not all(
    hasattr(t, "func") and hasattr(t, "name") for t in coordinator.tools
):
    raise SystemExit(
        "Upstream hat die Tool-Liste in analytics_mcp.coordinator geändert – "
        "_omf_remote/server.py muss angepasst werden."
    )


# --- 2. Anmeldung pro Person statt Server-Konto ------------------------------
def _user_credentials() -> Credentials:
    """Liefert die Google-Credentials der Person, die diese Anfrage stellt.

    Upstream ruft _get_credentials() bei jeder Client-Erstellung auf. Die
    Tools laufen per asyncio.to_thread; der Request-Kontext wird dabei
    mitkopiert, daher ist get_access_token() hier verfügbar.
    """
    token = get_access_token()
    if token is None or not token.token:
        raise PermissionError("Keine Google-Anmeldung für diese Anfrage vorhanden.")
    return Credentials(token=token.token)


ga_client._get_credentials = _user_credentials


# --- 3. Token-Speicher (verschlüsselt, persistent im Volume) -----------------
def _client_storage():
    from cryptography.fernet import Fernet
    from key_value.aio.stores.filetree import FileTreeStore
    from key_value.aio.wrappers.encryption.fernet import FernetEncryptionWrapper

    path = pathlib.Path(_env("GA4_MCP_STORAGE_PATH", "/data"))
    path.mkdir(parents=True, exist_ok=True)
    key = _env("GA4_MCP_STORAGE_ENCRYPTION_KEY", required=True)
    return FernetEncryptionWrapper(
        key_value=FileTreeStore(data_directory=path),
        fernet=Fernet(key.encode()),
        raise_on_decryption_error=False,
    )


# --- 4. Server mit Google-OAuth-Proxy ----------------------------------------
auth = GoogleProvider(
    client_id=_env("GA4_MCP_OAUTH_CLIENT_ID", required=True),
    client_secret=_env("GA4_MCP_OAUTH_CLIENT_SECRET", required=True),
    base_url=_env("GA4_MCP_BASE_URL", required=True),
    required_scopes=[
        "openid",
        "https://www.googleapis.com/auth/userinfo.email",
        "https://www.googleapis.com/auth/userinfo.profile",
        ANALYTICS_SCOPE,
    ],
    jwt_signing_key=_env("GA4_MCP_JWT_SIGNING_KEY", required=True),
    client_storage=_client_storage(),
)

mcp = FastMCP("Google Analytics MCP (OMF Remote)", auth=auth)

for adk_tool in coordinator.tools:
    mcp.tool(adk_tool.func, name=adk_tool.name, description=adk_tool.description)


def main() -> None:
    port = int(_env("PORT", "8080"))
    logger.info(
        "Starte GA4-MCP remote auf Port %s mit %d Tools: %s",
        port,
        len(coordinator.tools),
        ", ".join(t.name for t in coordinator.tools),
    )
    mcp.run(
        transport="streamable-http",
        host="0.0.0.0",
        port=port,
        uvicorn_config={"access_log": False},
    )


if __name__ == "__main__":
    main()

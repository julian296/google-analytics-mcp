"""Remote-Einstiegspunkt für den offiziellen Google-Analytics-MCP-Server.

Ergänzt googleanalytics/google-analytics-mcp um Streamable HTTP und eine
Google-Anmeldung pro Person (FastMCP OAuth-Proxy mit persistentem,
verschlüsseltem Token-Speicher) – nach demselben Muster wie der offizielle
Google-Ads-MCP-Server.

Diese Datei verändert keine Upstream-Datei. Sie
  1. übernimmt alle Lese-Tools, die upstream in
     analytics_mcp.coordinator.read_only_tools registriert (neue Lese-Tools
     kommen bei Updates automatisch mit; Schreib-Tools nie), und
  2. bindet jede Tool-Ausführung über die offizielle Upstream-Schnittstelle
     analytics_mcp.tools.client.use_request_access_token an das Google-Token
     der gerade angemeldeten Person. Zusätzlich ist upstream auf
     „Credentials pro Anfrage erforderlich“ gestellt, sodass nie auf ein
     Server-Konto (ADC) ausgewichen werden kann.

Read-only: angefordert wird nur der Scope analytics.readonly.
"""

import functools
import inspect
import logging
import os
import pathlib
import sys

from fastmcp import FastMCP
from fastmcp.server.auth.providers.google import GoogleProvider
from fastmcp.server.dependencies import get_access_token

import analytics_mcp.tools.client as ga_client
from analytics_mcp import coordinator

logger = logging.getLogger("omf_remote")
logging.basicConfig(level=logging.INFO, stream=sys.stderr)

ANALYTICS_SCOPE = "https://www.googleapis.com/auth/analytics.readonly"


def _env(
    name: str, default: str | None = None, required: bool = False
) -> str | None:
    value = os.environ.get(name, default)
    if required and not value:
        raise SystemExit(f"Umgebungsvariable {name} fehlt.")
    return value


# --- 1. Sicherheitsprüfung gegen Upstream-Änderungen -------------------------
# Wenn Google die Stelle umbaut, an der die Anmeldung entsteht, soll der Server
# nicht starten, statt stillschweigend auf eine andere Anmeldung auszuweichen.
for _name in ("use_request_access_token", "set_require_request_credentials"):
    if not callable(getattr(ga_client, _name, None)):
        raise SystemExit(
            f"Upstream hat analytics_mcp.tools.client.{_name} entfernt oder "
            "umbenannt – _omf_remote/server.py muss angepasst werden."
        )
_upstream_tools = getattr(coordinator, "read_only_tools", None)
if not _upstream_tools or not all(
    hasattr(t, "func")
    and hasattr(t, "name")
    and inspect.iscoroutinefunction(t.func)
    for t in _upstream_tools
):
    raise SystemExit(
        "Upstream hat die Tool-Liste in analytics_mcp.coordinator.read_only_tools "
        "geändert – _omf_remote/server.py muss angepasst werden."
    )


# --- 2. Anmeldung pro Person statt Server-Konto ------------------------------
# Upstream-Schalter: ohne Token pro Anfrage wird ein Fehler geworfen statt
# Application Default Credentials (Server-Konto) zu verwenden.
ga_client.set_require_request_credentials(True)


def _with_user_credentials(func):
    """Führt ein Upstream-Tool mit dem Google-Token der anfragenden Person aus.

    functools.wraps erhält Signatur und Docstring, damit FastMCP das
    Eingabeschema weiterhin aus der Upstream-Funktion erzeugt.
    """

    @functools.wraps(func)
    async def wrapper(*args, **kwargs):
        token = get_access_token()
        if token is None or not token.token:
            raise PermissionError(
                "Keine Google-Anmeldung für diese Anfrage vorhanden."
            )
        with ga_client.use_request_access_token(
            token.token, allow_write=False, require_request_credentials=True
        ):
            return await func(*args, **kwargs)

    return wrapper


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

for adk_tool in _upstream_tools:
    mcp.tool(
        _with_user_credentials(adk_tool.func),
        name=adk_tool.name,
        description=adk_tool.description,
    )


def main() -> None:
    port = int(_env("PORT", "8080"))
    logger.info(
        "Starte GA4-MCP remote auf Port %s mit %d Tools: %s",
        port,
        len(_upstream_tools),
        ", ".join(t.name for t in _upstream_tools),
    )
    if "--check" in sys.argv:
        # Startprüfung für CI: Importe, Schutzprüfungen und Tool-Registrierung
        # sind durchgelaufen – Server nicht wirklich starten.
        logger.info("Startprüfung erfolgreich.")
        return
    mcp.run(
        transport="streamable-http",
        host="0.0.0.0",
        port=port,
        uvicorn_config={"access_log": False},
    )


if __name__ == "__main__":
    main()

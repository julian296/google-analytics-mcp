# OMF Remote-Betrieb

Dieser Fork ergänzt den offiziellen Google-Analytics-MCP-Server um Remote-Betrieb
(Streamable HTTP unter `/mcp`) mit Google-Anmeldung pro Person. Upstream-Dateien
bleiben unverändert.

| Datei | Zweck |
| --- | --- |
| `_omf_remote/server.py` | Einstiegspunkt: OAuth-Proxy, Tools aus upstream, Nutzer-Token statt Server-Konto |
| `Dockerfile`, `.dockerignore` | Container für Coolify, Port 8080 |
| `.github/workflows/upstream-update.yml` | Wöchentlicher PR mit Änderungen aus upstream |

Der Ordnername beginnt mit `_`, damit setuptools ihn beim `pip install .` nicht als
zweites Paket erkennt.

## Umgebungsvariablen

| Variable | Pflicht | Beschreibung |
| --- | --- | --- |
| `GA4_MCP_OAUTH_CLIENT_ID` | ja | OAuth-Client (Webanwendung) aus Google Cloud |
| `GA4_MCP_OAUTH_CLIENT_SECRET` | ja | Zugehöriges Secret |
| `GA4_MCP_BASE_URL` | ja | Öffentliche URL ohne `/` am Ende, z. B. `https://ga4-mcp.fndry.space` |
| `GA4_MCP_JWT_SIGNING_KEY` | ja | Zufallsschlüssel (32 Byte, Base64) |
| `GA4_MCP_STORAGE_ENCRYPTION_KEY` | ja | Zweiter Zufallsschlüssel, Fernet-Format |
| `GA4_MCP_STORAGE_PATH` | nein | Token-Speicher, Standard `/data` (als Volume mounten) |
| `PORT` | nein | Standard `8080` |

Weiterleitungs-URI im OAuth-Client: `GA4_MCP_BASE_URL` + `/auth/callback`.

## Schutz bei Upstream-Updates

Der Server startet absichtlich nicht, wenn upstream `analytics_mcp.tools.client._get_credentials`
oder `analytics_mcp.coordinator.tools` umbaut. So kann ein Update nie still auf eine andere
Anmeldung ausweichen. Schlägt ein Deploy nach einem Update-PR fehl, im Log nach
„muss angepasst werden“ suchen.

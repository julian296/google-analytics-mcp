# OMF Remote-Betrieb

Dieser Fork ergänzt den offiziellen Google-Analytics-MCP-Server um Remote-Betrieb
(Streamable HTTP unter `/mcp`) mit Google-Anmeldung pro Person. Upstream-Dateien
bleiben unverändert.

| Datei | Zweck |
| --- | --- |
| `_omf_remote/server.py` | Einstiegspunkt: OAuth-Proxy, Tools aus upstream, Nutzer-Token statt Server-Konto |
| `Dockerfile` | Container für Coolify, Port 8080 (ersetzt das Dockerfile von upstream) |
| `.dockerignore` | Von upstream; OMF ergänzt nur die Freigabe von `_omf_remote/` |
| `.gitattributes` | `Dockerfile merge=ours`: bei Upstream-Merges bleibt das OMF-Dockerfile erhalten |
| `.github/workflows/upstream-update.yml` | Wöchentlicher PR mit Änderungen aus upstream inkl. Startprüfung (benötigt Repository-Secret `SYNC_TOKEN`) |

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

Der Server nutzt nur offizielle Upstream-Schnittstellen:

- `analytics_mcp.coordinator.read_only_tools` – alle Lese-Tools (Schreib-Tools werden nie registriert)
- `analytics_mcp.tools.client.use_request_access_token` – bindet das Google-Token der angemeldeten Person an jede Tool-Ausführung
- `analytics_mcp.tools.client.set_require_request_credentials(True)` – ohne Token pro Anfrage gibt es einen Fehler statt eines Rückfalls auf ein Server-Konto (ADC)

Der Server startet absichtlich nicht, wenn upstream eine dieser Stellen umbaut. So kann ein
Update nie still auf eine andere Anmeldung ausweichen. Schlägt ein Deploy nach einem
Update-PR fehl, im Log nach „muss angepasst werden“ suchen.

`python _omf_remote/server.py --check` führt alle Importe und Prüfungen aus, ohne den
Server zu starten. Der Upstream-Workflow nutzt das und schreibt das Ergebnis in den PR.

FastMCP muss zur `mcp`-Version von upstream passen (upstream ≥ 1.0: `mcp>=2.3` → `fastmcp>=4.1`).

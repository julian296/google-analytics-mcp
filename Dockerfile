# OMF-Ergänzung: Container für den Remote-Betrieb (Coolify, Port 8080)
#
# Dieses Dockerfile ersetzt bewusst das von upstream. Bei Upstream-Updates
# bleibt diese Fassung erhalten (siehe .gitattributes: merge=ours).
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8080

WORKDIR /app

COPY pyproject.toml README.md LICENSE ./
COPY analytics_mcp/ ./analytics_mcp/
COPY _omf_remote/ ./_omf_remote/

# Offizielles Paket aus dem Repo + FastMCP für HTTP und OAuth.
# FastMCP 4.1+ ist nötig, weil upstream mcp>=2.3 verlangt (FastMCP 3 nur mcp<2).
RUN pip install --no-cache-dir . "fastmcp>=4.1,<5"

EXPOSE 8080
CMD ["python", "_omf_remote/server.py"]

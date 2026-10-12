# OMF-Ergänzung: Container für den Remote-Betrieb (Coolify, Port 8080)
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8080

WORKDIR /app
COPY . .

# Offizielles Paket aus dem Repo + FastMCP für HTTP und OAuth
RUN pip install --no-cache-dir . "fastmcp>=3.2,<4"

EXPOSE 8080
CMD ["python", "_omf_remote/server.py"]

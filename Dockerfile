# =============================================================================
#  AQW Bot Hub -- web dashboard (browser mode, no GUI / pywebview needed)
# =============================================================================
#
#  Build:
#      docker build -t aqw-hub .
#
#  Run:
#      docker run -d --name aqw-hub -p 8080:8080 \
#          -e HUB_WEB_PASSWORD=tikuslu \
#          -v aqw-hub-data:/data \
#          aqw-hub
#
#  Or with compose (see docker-compose.yml):
#      docker compose up -d --build
#
#  Open http://<host>:8080 -- the browser asks for Basic Auth first.
#  (Any username; the password is HUB_WEB_PASSWORD.)
#
# -----------------------------------------------------------------------------
#  ENVIRONMENT VARIABLES
# -----------------------------------------------------------------------------
#  HUB_WEB_HOST       Bind address inside the container. Keep 0.0.0.0 so the
#                     published port is reachable from outside the container.
#                                                              default: 0.0.0.0
#  HUB_WEB_PORT       HTTP port the server listens on inside the container.
#                     Publish the same port with `-p <host>:<container>`.
#                                                              default: 8080
#  HUB_WEB_PASSWORD   Basic Auth password for the dashboard. ALWAYS required --
#                     if it is unset the app falls back to "tikuslu". CHANGE IT
#                     before exposing the port to the internet.
#                                                              default: tikuslu
#  HUB_DATA_DIR       Directory holding runtime files: players.json (the only
#                     place credentials are stored), gui_config.json,
#                     ultra_daily_config.json, ultra_speaker_config.json,
#                     weekly_doom_config.json, slavery/temple/eclipse configs.
#                     Mount a volume here so they survive image rebuilds /
#                     redeploys. /data is declared as a VOLUME below.
#                                                              default: /data
#  TZ                 Timezone, e.g. Asia/Jakarta, so script/log timestamps and
#                     "today" (daily/weekly resets) match your local time.
#                                                              default: UTC
#
#  NOTE: run one container per machine/instance. The bot actually drives the
#        AQW client over the network; it is not a static website.
# =============================================================================

FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    HUB_WEB_HOST=0.0.0.0 \
    HUB_WEB_PORT=8080 \
    HUB_WEB_PASSWORD=tikuslu \
    HUB_DATA_DIR=/data

WORKDIR /app

# Only what the engine + web server import at runtime. The GUI/build-only
# deps from requirements.txt are skipped on purpose (pywebview would also need
# GTK/WebView system libraries that a headless server does not have).
RUN python -m pip install --no-cache-dir \
        "colorama>=0.4.6" \
        "python-dotenv>=1.0.1" \
        "Requests>=2.32.3" \
        "psutil>=5.9.0" \
        "bottle>=0.13.0" \
        "Pillow>=10.0.0"

# Engine + dashboard code. Credentials and personal configs are excluded via
# .dockerignore and injected at runtime through the /data volume.
COPY . /app

# Safety net: a developer's working copy of bot/ultra/config.py may hold the real
# ultra logins even though the tracked file has placeholders. Put the
# placeholders back so nothing secret ever ends up in the image layer.
RUN python docker/scrub_credentials.py /app

# Persistent storage for players.json / *_config.json.
VOLUME ["/data"]
EXPOSE 8080

# Server is healthy when the authenticated log endpoint answers 200.  The
# start period is generous because a low CPU_LIMIT stretches the boot: at
# cpus=0.1 the engine import alone can take ~30s.
HEALTHCHECK --interval=30s --timeout=5s --start-period=90s --retries=3 \
    CMD python -c "import os,base64,urllib.request; r=urllib.request.Request('http://127.0.0.1:'+os.environ.get('HUB_WEB_PORT','8080')+'/api/logs'); r.add_header('Authorization','Basic '+base64.b64encode(('hub:'+os.environ.get('HUB_WEB_PASSWORD','tikuslu')).encode()).decode()); urllib.request.urlopen(r,timeout=4)" || exit 1

CMD ["python", "app/build_hub_app.py", "web"]

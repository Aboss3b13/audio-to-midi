#!/usr/bin/env bash
set -euo pipefail

read -r SUDO_PASSWORD
printf '%s\n' "$SUDO_PASSWORD" | sudo -S -v
unset SUDO_PASSWORD

NGINX_SITE=/etc/nginx/sites-available/default
APP_ROOT=/home/abbas/scoreflow

if ! grep -q 'location = /Music' "$NGINX_SITE"; then
    sudo cp "$NGINX_SITE" "${NGINX_SITE}.scoreflow.$(date +%Y%m%d_%H%M%S).bak"
    sudo APP_ROOT="$APP_ROOT" NGINX_SITE="$NGINX_SITE" python3 - <<'PY'
import os
from pathlib import Path

site_path = Path(os.environ["NGINX_SITE"])
site = site_path.read_text()
needle = r"    location ~ \.php"
if site.count(needle) != 2:
    raise RuntimeError(f"Expected two PHP location markers, found {site.count(needle)}")

raw = (Path(os.environ["APP_ROOT"]) / "deploy" / "nginx-music.conf").read_text()
snippet = raw[raw.index("location ="):].strip()
site_path.write_text(site.replace(needle, f"{snippet}\n\n{needle}"))
PY
fi

if ! grep -q 'client_max_body_size 500m' "$NGINX_SITE"; then
    sudo NGINX_SITE="$NGINX_SITE" python3 - <<'PY'
import os
from pathlib import Path

site_path = Path(os.environ["NGINX_SITE"])
site = site_path.read_text()
needle = "location ^~ /Music/ {\n"
if site.count(needle) != 2:
    raise RuntimeError(f"Expected two Music proxy locations, found {site.count(needle)}")
settings = "    client_max_body_size 500m;\n    client_body_timeout 600s;\n"
site_path.write_text(site.replace(needle, needle + settings))
PY
fi

sudo nginx -t
sudo systemctl reload nginx

curl --fail --silent --show-error http://127.0.0.1:8502/Music/_stcore/health

#!/usr/bin/env bash
# Cloudflare tunnel for sarkariworld.com -> this machine.
#
#   sarkariworld.com      -> 127.0.0.1:7701  (Next.js site, PM2 "sarkariworld-website")
#   api.sarkariworld.com  -> 127.0.0.1:7700  (FastAPI,      PM2 "sarkariworld-api-py")
#
# Run `cloudflared tunnel login` FIRST — it opens a browser to pick the zone
# and writes ~/.cloudflared/cert.pem. This script does everything after that,
# and is safe to re-run.
set -euo pipefail

TUNNEL_NAME="sarkariworld"
CF_DIR="$HOME/.cloudflared"
CONFIG="$CF_DIR/config.yml"
CLOUDFLARED="$(command -v cloudflared)"

if [ ! -f "$CF_DIR/cert.pem" ]; then
  echo "ERROR: $CF_DIR/cert.pem missing. Run this first, then re-run me:" >&2
  echo "  cloudflared tunnel login" >&2
  exit 1
fi

# 1. Create the tunnel (idempotent).
if cloudflared tunnel list --output json | grep -q "\"name\":\"$TUNNEL_NAME\""; then
  echo "==> tunnel '$TUNNEL_NAME' already exists"
else
  echo "==> creating tunnel '$TUNNEL_NAME'"
  cloudflared tunnel create "$TUNNEL_NAME"
fi

UUID="$(cloudflared tunnel list --output json \
  | python3 -c "import json,sys;print(next(t['id'] for t in json.load(sys.stdin) if t['name']=='$TUNNEL_NAME'))")"
echo "==> tunnel id: $UUID"

# 2. Ingress config. First match wins; the catch-all 404 must stay last.
echo "==> writing $CONFIG"
cat > "$CONFIG" <<YAML
tunnel: $UUID
credentials-file: $CF_DIR/$UUID.json

# Cloudflare terminates TLS and reaches these plain-HTTP local ports. Both
# services bind 127.0.0.1 only, so this tunnel is their sole public entrance.
ingress:
  - hostname: api.sarkariworld.com
    service: http://127.0.0.1:7700
  - hostname: sarkariworld.com
    service: http://127.0.0.1:7701
  # To also serve www, add the hostname here AND run:
  #   cloudflared tunnel route dns $TUNNEL_NAME www.sarkariworld.com
  # - hostname: www.sarkariworld.com
  #   service: http://127.0.0.1:7701
  - service: http_status:404
YAML

# 3. DNS. Deliberately no --overwrite-dns: if a record already exists this
#    fails loudly rather than silently repointing a live domain.
for host in api.sarkariworld.com sarkariworld.com; do
  echo "==> routing $host"
  cloudflared tunnel route dns "$TUNNEL_NAME" "$host" || {
    echo "    (already routed, or a conflicting record exists —" >&2
    echo "     check the Cloudflare DNS tab, or re-run that one command" >&2
    echo "     with --overwrite-dns if you are sure)" >&2
  }
done

# 4. Run it under PM2, alongside the two app processes.
cat > "$CF_DIR/pm2-tunnel.config.cjs" <<PM2
module.exports = {
  apps: [{
    name: "cloudflared-tunnel",
    script: "$CLOUDFLARED",
    args: "tunnel --config $CONFIG --no-autoupdate run $TUNNEL_NAME",
    interpreter: "none",
    exec_mode: "fork",
    instances: 1,
    autorestart: true,
    max_restarts: 20,
    out_file: "$CF_DIR/tunnel-out.log",
    error_file: "$CF_DIR/tunnel-error.log",
    time: true,
  }],
};
PM2

pm2 delete cloudflared-tunnel 2>/dev/null || true
pm2 start "$CF_DIR/pm2-tunnel.config.cjs"
pm2 save

echo
echo "==> done. Verify:"
echo "     curl -sS https://api.sarkariworld.com/health"
echo "     curl -sSI https://sarkariworld.com | head -1"

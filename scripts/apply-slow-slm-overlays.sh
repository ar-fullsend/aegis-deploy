#!/usr/bin/env bash
# Deploy manifests/slow-slm overlays (latest version) so local SLM timeouts
# stay above stock v1.0.0 builtins that core re-registers on startup.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(dirname "$SCRIPT_DIR")"
OVERLAY_DIR="$ROOT_DIR/manifests/slow-slm"
RUNTIME_URL="${AEGIS_RUNTIME_URL:-http://127.0.0.1:8088}"
KEYCLOAK_URL="${KEYCLOAK_URL:-http://127.0.0.1:8180}"

if [[ -f "$ROOT_DIR/.env" ]]; then
    set -a
    # shellcheck source=/dev/null
    source "$ROOT_DIR/.env"
    set +a
fi

echo "==> Waiting for runtime at $RUNTIME_URL/health ..."
for i in $(seq 1 60); do
    if curl -sf --max-time 3 "$RUNTIME_URL/health" >/dev/null 2>&1; then
        echo "    runtime is up"
        break
    fi
    if [[ "$i" -eq 60 ]]; then
        echo "ERROR: runtime not healthy after 60s at $RUNTIME_URL/health"
        exit 1
    fi
    sleep 2
done

echo "==> Requesting Keycloak token ..."
CLIENT_SECRET="${KEYCLOAK_CLIENT_SECRET:-placeholder}"
TOKEN=$(curl -sS -X POST "$KEYCLOAK_URL/realms/aegis-system/protocol/openid-connect/token" \
    -H "Content-Type: application/x-www-form-urlencoded" \
    -d "client_id=aegis-runtime" \
    --data-urlencode "client_secret=${CLIENT_SECRET}" \
    -d "grant_type=client_credentials" \
    | python3 -c "import sys,json; print(json.load(sys.stdin)['access_token'])")

if [[ -z "$TOKEN" || "$TOKEN" == "null" ]]; then
    echo "ERROR: could not obtain access token from $KEYCLOAK_URL"
    exit 1
fi

export AEGIS_KEY="$TOKEN"
export AEGIS_API_TOKEN="$TOKEN"
export AEGIS_HOST=127.0.0.1
export AEGIS_PORT=8088

AEGIS_BIN="${AEGIS_BIN:-$HOME/.local/bin/aegis}"
if [[ ! -x "$AEGIS_BIN" ]]; then
    AEGIS_BIN="$(command -v aegis || true)"
fi
if [[ -z "$AEGIS_BIN" ]]; then
    echo "ERROR: aegis CLI not found"
    exit 1
fi

echo "==> Deploying slow-slm agent overlays ..."
shopt -s nullglob
agents=("$OVERLAY_DIR"/aegis-*-agent.yaml)
if [[ ${#agents[@]} -eq 0 ]]; then
    echo "ERROR: no agent overlays in $OVERLAY_DIR"
    exit 1
fi
for f in "${agents[@]}"; do
    echo "    agent $(basename "$f")"
    "$AEGIS_BIN" --host 127.0.0.1 --port 8088 agent deploy --force "$f"
done

echo "==> Deploying slow-slm workflow overlay ..."
"$AEGIS_BIN" --host 127.0.0.1 --port 8088 workflow deploy --force --scope global \
    "$OVERLAY_DIR/builtin-intent-to-execution.yaml"

echo "==> Slow-SLM overlays applied (latest = overlay version in $OVERLAY_DIR)"

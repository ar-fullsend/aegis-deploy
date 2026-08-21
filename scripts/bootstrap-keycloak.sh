#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(dirname "$SCRIPT_DIR")"

if [[ -f "$ROOT_DIR/.env" ]]; then
    set -a
    source "$ROOT_DIR/.env"
    set +a
fi

KEYCLOAK_URL="${KEYCLOAK_URL:-http://localhost:8180}"
REALM="${AEGIS_REALM:-aegis-system}"
ADMIN_USER="${KEYCLOAK_ADMIN:-admin}"
ADMIN_PASS="${KEYCLOAK_ADMIN_PASSWORD:-changeme}"

echo "==> Bootstrapping Keycloak at $KEYCLOAK_URL (realm: $REALM)"

# Wait for Keycloak to be ready
echo "Waiting for Keycloak to become ready (this can take 30-90s on first start)..."
for i in $(seq 1 30); do
  if curl -sf --max-time 5 "$KEYCLOAK_URL/health/ready" > /dev/null 2>&1; then
    echo "Keycloak is ready."
    break
  fi
  echo -n "."
  sleep 5
  if [ $i -eq 30 ]; then
    echo "ERROR: Keycloak did not become ready in time. Check pod logs."
    exit 1
  fi
done
echo

# Get admin token
ADMIN_TOKEN=$(curl -s -X POST "$KEYCLOAK_URL/realms/master/protocol/openid-connect/token" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=$ADMIN_USER" \
  -d "password=$ADMIN_PASS" \
  -d "grant_type=password" \
  -d "client_id=admin-cli" | jq -r '.access_token')

if [[ "$ADMIN_TOKEN" == "null" || -z "$ADMIN_TOKEN" ]]; then
  echo "ERROR: Failed to get admin token. Is Keycloak up and admin password correct?"
  exit 1
fi

echo "Got admin token"

# Create realm if not exists
curl -s -X POST "$KEYCLOAK_URL/admin/realms" \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "realm": "'$REALM'",
    "enabled": true,
    "displayName": "AEGIS System",
    "sslRequired": "external",
    "registrationAllowed": false,
    "loginWithEmailAllowed": true,
    "duplicateEmailsAllowed": false,
    "resetPasswordAllowed": true,
    "editUsernameAllowed": false,
    "bruteForceProtected": true
  }' || true

echo "Realm $REALM created or already exists"

# Create client for temporal worker (with audience mapper for correct 'aud' claim)
curl -s -X POST "$KEYCLOAK_URL/admin/realms/$REALM/clients" \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "clientId": "aegis-temporal-worker",
    "enabled": true,
    "publicClient": false,
    "directAccessGrantsEnabled": true,
    "serviceAccountsEnabled": true,
    "standardFlowEnabled": true,
    "secret": "placeholder",
    "protocolMappers": [{
      "name": "aegis-aud-mapper",
      "protocol": "openid-connect",
      "protocolMapper": "oidc-audience-mapper",
      "consentRequired": false,
      "config": {
        "included.client.audience": "aegis-orchestrator",
        "id.token.claim": "false",
        "access.token.claim": "true"
      }
    }]
  }' || true

echo "Client aegis-temporal-worker created or exists"

# Create client for the runtime if needed (with audience mapper)
curl -s -X POST "$KEYCLOAK_URL/admin/realms/$REALM/clients" \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "clientId": "aegis-runtime",
    "enabled": true,
    "publicClient": false,
    "directAccessGrantsEnabled": true,
    "serviceAccountsEnabled": true,
    "standardFlowEnabled": true,
    "secret": "placeholder",
    "protocolMappers": [{
      "name": "aegis-aud-mapper",
      "protocol": "openid-connect",
      "protocolMapper": "oidc-audience-mapper",
      "consentRequired": false,
      "config": {
        "included.client.audience": "aegis-orchestrator",
        "id.token.claim": "false",
        "access.token.claim": "true"
      }
    }]
  }' || true

echo "Client aegis-runtime created or exists"

# Create custom client scopes needed by runtime + temporal worker
API_SCOPES=(
  "agent:list" "agent:read" "agent:execute" "agent:deploy" "agent:update"
  "execution:read" "execution:stream"
  "workflow:read" "workflow:list" "workflow:run" "workflow:execute"
  "volume:read" "volume:write"
)
for SCOPE in "${API_SCOPES[@]}"; do
  curl -s -X POST "$KEYCLOAK_URL/admin/realms/$REALM/client-scopes" \
    -H "Authorization: Bearer $ADMIN_TOKEN" \
    -H "Content-Type: application/json" \
    -d "{\"name\":\"$SCOPE\",\"protocol\":\"openid-connect\",\"attributes\":{\"include.in.token.scope\":\"true\"}}" || true
done
echo "Custom scopes created (or already exist)"

ALL_SCOPES=$(curl -s "$KEYCLOAK_URL/admin/realms/$REALM/client-scopes" -H "Authorization: Bearer $ADMIN_TOKEN")
assign_scopes() {
  local client_id="$1"
  local uuid
  uuid=$(curl -s "$KEYCLOAK_URL/admin/realms/$REALM/clients?clientId=$client_id" \
    -H "Authorization: Bearer $ADMIN_TOKEN" | python3 -c "import sys,json; c=json.load(sys.stdin); print(c[0]['id'] if c else '')" 2>/dev/null)
  if [[ -z "$uuid" ]]; then
    echo "WARN: client $client_id not found"
    return
  fi
  for SCOPE in "${API_SCOPES[@]}"; do
    SCOPE_ID=$(echo "$ALL_SCOPES" | python3 -c "import sys,json; s={x['name']:x['id'] for x in json.load(sys.stdin)}; print(s.get('$SCOPE',''))" 2>/dev/null)
    if [[ -n "$SCOPE_ID" ]]; then
      curl -s -X PUT "$KEYCLOAK_URL/admin/realms/$REALM/clients/$uuid/default-client-scopes/$SCOPE_ID" \
        -H "Authorization: Bearer $ADMIN_TOKEN" -o /dev/null
    fi
  done
  echo "Scopes assigned to $client_id"
}
assign_scopes aegis-temporal-worker
assign_scopes aegis-runtime

echo "==> Keycloak bootstrap complete (basic realm and clients)"
echo "You may need to create users, roles, and additional clients via the admin console at $KEYCLOAK_URL"

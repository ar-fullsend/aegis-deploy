#!/usr/bin/env bash
set -euo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
NC='\033[0m'

check_http() {
    local name="$1" url="$2"
    if curl -sf --max-time 5 "$url" > /dev/null 2>&1; then
        echo -e "  ${GREEN}✓${NC} $name"
    else
        echo -e "  ${RED}✗${NC} $name ($url)"
    fi
}

check_cmd() {
    local name="$1"
    shift
    if "$@" > /dev/null 2>&1; then
        echo -e "  ${GREEN}✓${NC} $name"
    else
        echo -e "  ${RED}✗${NC} $name"
    fi
}

check_tcp() {
    local name="$1" host="$2" port="$3"
    if timeout 3 bash -c "exec 3<>/dev/tcp/$host/$port" 2>/dev/null; then
        echo -e "  ${GREEN}✓${NC} $name"
    else
        echo -e "  ${RED}✗${NC} $name (tcp $host:$port)"
    fi
}

# Load environment (for POSTGRES_USER etc.)
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
if [[ -f "$ROOT_DIR/.env" ]]; then
    set -a
    # shellcheck source=/dev/null
    source "$ROOT_DIR/.env"
    set +a
fi

# Load profile so we only validate components that are supposed to be deployed.
# Respects PROFILE env var (e.g. PROFILE=full make validate) or first arg.
PROFILE="${PROFILE:-${1:-development}}"
PROFILE_FILE="$ROOT_DIR/profiles/${PROFILE}.conf"
if [[ -f "$PROFILE_FILE" ]]; then
    # shellcheck source=/dev/null
    source "$PROFILE_FILE"
else
    echo "WARNING: Profile file '$PROFILE_FILE' not found, falling back to development."
    PODS="database secrets temporal seal-gateway core observability"
fi

# For easy substring matching: " database secrets ..."
PODS_LIST=" $PODS "

has_pod() {
    [[ "$PODS_LIST" == *" $1 "* ]]
}

echo "Validating AEGIS platform services... (profile: $PROFILE)"
echo ""

if has_pod database; then
    echo "Database:"
    # Matches the readinessProbe in pod-database.yaml (postgres container)
    check_cmd "PostgreSQL" podman exec aegis-database-postgres pg_isready -U "${POSTGRES_USER:-aegis}"
    # Most AEGIS services connect via pgbouncer on 5433 (pooled)
    check_tcp "PgBouncer (5433)" localhost 5433
fi

if has_pod core; then
    echo "Core:"
    check_http "AEGIS Runtime" "http://localhost:8088/health"
fi

if has_pod temporal; then
    echo "Temporal:"
    check_http "Temporal UI" "http://localhost:8233"
    # Use the internal service DNS name (works from inside the container); localhost does not.
    # Matches the approach used by the temporal-ui container and the readiness probe.
    check_cmd "Temporal Server" podman exec aegis-temporal-temporal temporal operator cluster health --address aegis-temporal:7233
fi

if has_pod seal-gateway; then
    echo "Gateways:"
    check_http "SEAL Gateway" "http://localhost:8089"
fi

echo "IAM & Secrets:"
if has_pod iam; then
    check_http "Keycloak" "http://localhost:8180/health/ready"
else
    echo -e "  ${GREEN}○${NC} Keycloak (not in profile)"
fi
if has_pod secrets; then
    check_http "OpenBao" "http://localhost:8200/v1/sys/health"
fi

if has_pod observability; then
    echo "Observability:"
    check_http "Jaeger UI" "http://localhost:16686"
    check_http "Prometheus" "http://localhost:9090/-/ready"
    check_http "Grafana" "http://localhost:3300/api/health"
    check_http "Loki" "http://localhost:3100/ready"
fi

if has_pod storage; then
    echo "Storage:"
    check_http "SeaweedFS Master" "http://localhost:9333"
    check_http "SeaweedFS Filer" "http://localhost:8888"
fi

echo ""
echo "Run 'make status' for pod-level status."

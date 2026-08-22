#!/usr/bin/env bash
# Point host.containers.internal at the host LAN IPv4 inside aegis-core.
# On Kali + netavark, Podman injects 169.254.1.2 which times out from the
# bridge network. LM Studio and the FUSE daemon bind 0.0.0.0 on the host.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib/host-lan-ip.sh
source "$SCRIPT_DIR/lib/host-lan-ip.sh"

CONTAINER="${1:-aegis-core-aegis-runtime}"
HOST_IP="${AEGIS_HOST_LAN_IP:-$(detect_host_lan_ip)}"

if [[ -z "$HOST_IP" ]]; then
    echo "ERROR: could not detect host LAN IP (set AEGIS_HOST_LAN_IP)"
    exit 1
fi

if ! podman container exists "$CONTAINER" 2>/dev/null; then
    echo "WARN: $CONTAINER not running — skip host.containers.internal patch"
    exit 0
fi

echo "  -> Mapping host.containers.internal -> $HOST_IP in $CONTAINER"
podman exec -u 0 "$CONTAINER" sh -c "
HOSTIP='$HOST_IP'
awk -v ip=\"\$HOSTIP\" '
  BEGIN { done = 0 }
  /host.containers.internal/ {
    print ip \" host.containers.internal host.docker.internal\"
    done = 1
    next
  }
  { print }
  END { if (!done) print ip \" host.containers.internal host.docker.internal\" }
' /etc/hosts > /tmp/hosts.new
cat /tmp/hosts.new > /etc/hosts
" >/dev/null

if podman exec "$CONTAINER" curl -sf --max-time 5 "http://host.containers.internal:1234/v1/models" >/dev/null 2>&1; then
    echo "  -> host.containers.internal:1234 reachable (LM Studio)"
else
    echo "WARN: host.containers.internal:1234 not reachable from $CONTAINER"
    echo "      Bind LM Studio to 0.0.0.0 and confirm the host firewall allows $HOST_IP:1234"
fi

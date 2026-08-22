# Detect the host IPv4 that containers can hairpin to on a netavark bridge.
# pasta's host.containers.internal (169.254.1.2) is unreachable from aegis-network.
detect_host_lan_ip() {
    ip -4 route get 1.1.1.1 2>/dev/null \
        | awk '{for (i = 1; i <= NF; i++) if ($i == "src") { print $(i + 1); exit }}'
}

if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    detect_host_lan_ip
fi

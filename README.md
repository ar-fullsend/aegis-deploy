# aegis-deploy

Podman-based deployment for the [AEGIS](https://docs.100monkeys.ai) platform.

## Prerequisites

- **Ubuntu 22.04/24.04 or Kali** (Kali uses native Podman packages; `make setup` detects it)
- **Podman 4.0+** (rootless) -- `make setup` installs this on supported distros
- **GitHub PAT** with `read:packages` (or `gh auth`) for pulling images from `ghcr.io/100monkeys-ai`
- Optional local LLM: [LM Studio](https://lmstudio.ai) on `0.0.0.0:1234` (infra comes up without a model)

## Quick Start

```bash
git clone https://github.com/ar-fullsend/aegis-deploy.git
cd aegis-deploy
cp .env.example .env        # set AEGIS_ROOT, GHCR_*, POSTGRES_PASSWORD
make setup                   # install Podman + dependencies
make deploy                  # development profile (includes IAM)
make bootstrap-keycloak      # realm + clients (idempotent)
make generate-keys           # SEAL RSA keys
make status && make validate
```

OpenBao bootstrap runs automatically after the secrets pod. See [docs/LOCAL-OPS.md](docs/LOCAL-OPS.md) for JWT, LM Studio, Grafana scrapes, and agent vs Temporal.

## Deployment Profiles

Select a profile with `PROFILE=<name> make deploy`. Default: `development`.

| Profile | Pods | Use Case |
|---|---|---|
| `minimal` | secrets, core | Local development with external DB |
| `development` | database, secrets, temporal, seal-gateway, iam, core, mcp, storage, observability | Full local dev (includes IAM + SeaweedFS + MCP) |
| `full` | database, secrets, storage, temporal, seal-gateway, core, mcp, observability | Complete platform storage path (**no** iam in profile) |

`edge` is optional and not in any profile: `make redeploy POD=edge`.

## Pod Architecture

| Pod | Services | Ports |
|---|---|---|
| **pod-core** | aegis-runtime + metrics-proxy | 8088 (HTTP), 50051 (gRPC), 2049 (NFS), 9091 (loopback metrics), 9092 (Prometheus scrape) |
| **pod-database** | PostgreSQL 15, postgres-exporter | 5432, 9187 |
| **pod-secrets** | OpenBao | 8200 |
| **pod-temporal** | Temporal 1.23 (auto-setup), Temporal UI 2.21, aegis-temporal-worker | 7233 (gRPC), 8233 (UI) |
| **pod-iam** | Keycloak 24 | 8180 |
| **pod-seal-gateway** | aegis-seal-gateway | 8089 (HTTP), 50055 (gRPC) |
| **pod-mcp** | zaru-mcp-server ([aegis-mcp-tools](https://github.com/100monkeys-ai/aegis-mcp-tools)) | 8090 (MCP StreamableHTTP `/mcp/v1`) |
| **pod-observability** | Jaeger 1.55, Prometheus 2.51, Grafana 10.4, Loki 3.0, Promtail 3.0, otelcol-contrib 0.99 | 16686 (Jaeger UI), 4317/4318 (OTLP → otelcol), 9090 (Prometheus), 3300 (Grafana), 3100 (Loki) |
| **pod-storage** | SeaweedFS (master, volume, filer, WebDAV) | 9333 (master), 8080 (volume), 8888 (filer), 7333 (WebDAV) |
| **host** | FUSE daemon (FuseMountService gRPC) | 50053 — runs on the host as a systemd user service, not in a pod |

All pods join the `aegis-network` bridge network.

## FUSE Daemon (Host-Side Storage)

The AEGIS FUSE daemon is a **host-side** component -- it runs on the host as a
systemd user service, not inside a container. It provides native POSIX
filesystem access to workspace volumes via the FSAL security boundary.

Rootless Podman containers cannot mount FUSE filesystems internally, so the
daemon runs on the host and exposes mountpoints that are bind-mounted into
execution containers. This gives agents transparent read/write access to their
workspace files.

### Architecture

- Connects to the orchestrator's gRPC endpoint for FSAL operations
- Mounts workspace volumes as FUSE filesystems on the host
- Execution containers access files through bind mounts from FUSE mountpoints
- All operations pass through the FSAL security boundary (tenant isolation,
  access policies)

### Management

The daemon is started automatically by `make deploy` and managed via systemd:

```bash
systemctl --user start aegis-fuse-daemon
systemctl --user stop aegis-fuse-daemon
systemctl --user status aegis-fuse-daemon
journalctl --user -u aegis-fuse-daemon -f   # tail logs
```

### Prerequisites

Requires the `fuse3` package and `fuse` kernel module. The unit runs
`%h/.local/bin/aegis` (extracted from the runtime image into `$REPO/bin/aegis`).
It retries until orchestrator `:50051` is up.

## Edge Proxy (Optional)

The `pod-edge` directory contains a Caddy reverse proxy.

**Local (default in this repo):** HTTP on port 80, `auto_https off`, no Cloudflare token required. Hostnames use `DOMAIN_*` from `.env` (defaults `*.localhost`).

| Subdomain Variable | Default | Backend (in-pod port) |
|---|---|---|
| `DOMAIN_API` | `api.localhost` | aegis-core:8088 |
| `DOMAIN_SEAL` | `seal.localhost` | aegis-seal-gateway:8089 |
| `DOMAIN_MCP` | `mcp.localhost` | aegis-mcp:**3000** (host maps 8090→3000) |
| `DOMAIN_TEMPORAL` | `temporal.localhost` | aegis-temporal:8080 |
| `DOMAIN_GRAFANA` | `grafana.localhost` | aegis-observability:**3000** (host maps 3300→3000) |
| `DOMAIN_PROMETHEUS` | `prometheus.localhost` | aegis-observability:9090 |
| `DOMAIN_JAEGER` | `jaeger.localhost` | aegis-observability:16686 |
| `DOMAIN_SECRETS` | `secrets.localhost` | aegis-secrets:8200 |

**Production TLS:** restore Cloudflare ACME (`acme_dns cloudflare`) and set `CLOUDFLARE_API_TOKEN` + real `DOMAIN_*`.

```bash
make redeploy POD=edge
```

## WSL2 / Windows browser access

If the stack runs in **WSL2**, Windows browser `http://127.0.0.1:PORT` hits **Windows**, not WSL → connection refused.

- Inside WSL: `http://127.0.0.1:PORT` is correct.
- From Windows browser: use the WSL eth0 IP (`hostname -I` inside WSL), e.g. `http://172.27.70.12:3300` for Grafana.

See [docs/LOCAL-OPS.md](docs/LOCAL-OPS.md) for the full UI port list, LLM config, JWT auth, and workflow YAML schema.

## Local LLM (LM Studio)

`podman/pods/core/aegis-config.yaml` is **prefer-local**:

- Host server: `http://127.0.0.1:1234` — bind **`0.0.0.0`** (`lms server start --bind 0.0.0.0`). `127.0.0.1` is unreachable from pods.
- From pods: `http://host.containers.internal:1234/v1`
- Model: `prism-ml/bonsai-27b` (confirm with `curl -s http://127.0.0.1:1234/v1/models`)
- Aliases `default`, `slm`, `smart`, `judge`, `slm-judge` all point at Bonsai (`max_output_tokens` 8192; thinking models spend tokens on `reasoning_content` first)
- Gemini stays `enabled: false` unless `ZARU_LLM_API_KEY` is set

After config changes: `podman restart aegis-core-aegis-runtime`.

## Makefile Targets

| Target | Description |
|---|---|
| `make setup` | Install Podman and dependencies (Ubuntu or Kali) |
| `make deploy` | Deploy all pods for the active profile |
| `make teardown` | Stop and remove all pods for the active profile |
| `make status` | Show running pod status |
| `make validate` | Run health checks against deployed services |
| `make registry-login` | Authenticate to ghcr.io using `.env` credentials |
| `make bootstrap-secrets` | Initialize OpenBao and populate AppRole credentials |
| `make bootstrap-keycloak` | Configure Keycloak realm, clients, and roles |
| `make generate-keys` | Generate SEAL RSA signing key pair |
| `make redeploy POD=<name>` | Tear down and redeploy a single pod |
| `make logs POD=<name>` | Tail logs for a specific pod |
| `make clean` | Full teardown + prune volumes and networks |

## Configuration

Copy `.env.example` to `.env` and fill in the required values. Key variables:

| Variable | Required | Description |
|---|---|---|
| `AEGIS_ROOT` | Yes | Absolute path to this repository checkout |
| `GHCR_USERNAME` | Yes | GitHub username for container registry |
| `GHCR_TOKEN` | Yes | GitHub PAT with `read:packages` scope |
| `POSTGRES_PASSWORD` | Yes | PostgreSQL password |
| `ZARU_LLM_API_KEY` | No | Gemini key; unused while Gemini is disabled |
| `KEYCLOAK_ADMIN_PASSWORD` | Recommended | Keycloak admin password (default: `changeme`) |
| `GRAFANA_ADMIN_PASSWORD` | Recommended | Grafana admin password (default: `changeme`) |
| `CLOUDFLARE_API_TOKEN` | Edge only | Required for Caddy TLS via DNS challenge |

See `.env.example` for the full list with descriptions.

## Using the CLI with a local deployment

After `make deploy PROFILE=development` (which now includes the `iam` pod) and `make bootstrap-keycloak`:

```bash
# Non-interactive JWT (AEGIS_API_TOKEN is not a JWT and will 401).
# Client secret from bootstrap-keycloak.sh is "placeholder".
TOKEN=$(curl -sS -X POST 'http://127.0.0.1:8180/realms/aegis-system/protocol/openid-connect/token' \
  -H 'Content-Type: application/x-www-form-urlencoded' \
  -d 'client_id=aegis-runtime&client_secret=placeholder&grant_type=client_credentials' \
  | python3 -c 'import sys,json;print(json.load(sys.stdin)["access_token"])')

# Direct agent execute (in-process — does NOT appear in Temporal UI)
AEGIS_KEY="$TOKEN" aegis --host 127.0.0.1 --port 8088 --output json \
  agent run aegis-python-executor-agent \
  --intent 'Write a Python function fib(n) that returns the first n Fibonacci numbers.'

# Durable workflow (DOES appear at http://127.0.0.1:8233/namespaces/default/workflows)
AEGIS_KEY="$TOKEN" aegis --host 127.0.0.1 --port 8088 --output json \
  workflow run builtin-intent-to-execution \
  --intent 'Write a Python function fib(n).' \
  --input '{"language":"python","language_ext":"py","runner":"python3","runner_flags":"-s","container_image":"python:3.11-slim","inputs":{"n":10},"inputs_json":"{\"n\":10}"}'
```

`hello-world` is deployed but cannot start (schema requires `task`; the execute path wraps input). Use `aegis-python-executor-agent` or a Temporal workflow. See [docs/LOCAL-OPS.md](docs/LOCAL-OPS.md).

## Documentation

Full platform documentation: <https://docs.100monkeys.ai>

## License

[AGPL-3.0-only](LICENSE) -- Copyright 2026 [100monkeys.ai](https://100monkeys.ai)

# AGENTS.md — aegis-deploy

AI assistant context for the **aegis-deploy** repository. `CLAUDE.md` is a symlink to this file.

## What This Repository Is

`aegis-deploy` is the **Podman-based deployment orchestration** layer for the [AEGIS platform](https://docs.100monkeys.ai) (100monkeys.ai). It contains no application source code — only:

- Kubernetes-style pod YAML files consumed by `podman play kube`
- Bash deployment scripts and a Makefile entry point
- Configuration files for each service
- Deployment profiles that select which pods to run
- A systemd user service for the FUSE daemon

The primary technology is **rootless Podman 4.0+** running on **Ubuntu 22.04/24.04**. There is no Node.js, Python, or compiled code to build in this repo.

## Repository Layout

```
aegis-deploy/
├── Makefile                     # Primary entry point — all workflows run through make
├── .env.example                 # Environment variable template; copy to .env
├── profiles/
│   ├── minimal.conf             # PODS="secrets core"
│   ├── development.conf         # PODS="database secrets temporal seal-gateway iam core storage observability"
│   └── full.conf                # PODS="database secrets storage temporal seal-gateway core observability"
├── podman/
│   ├── networks/create-networks.sh  # Creates aegis-network bridge
│   └── pods/                    # One directory per pod
│       ├── core/
│       │   ├── pod-core.yaml        # aegis-runtime pod definition
│       │   ├── aegis-config.yaml    # Runtime config (LLM, DB, Temporal, tracing)
│       │   └── runtime-registry.yaml
│       ├── database/pod-database.yaml
│       ├── secrets/pod-secrets.yaml
│       ├── temporal/pod-temporal.yaml
│       ├── seal-gateway/
│       │   ├── pod-seal-gateway.yaml
│       │   └── seal-gateway-config.yaml
│       ├── iam/pod-iam.yaml
│       ├── observability/
│       │   ├── pod-observability.yaml
│       │   ├── prometheus.yaml      # Scrape config
│       │   ├── loki-config.yaml
│       │   ├── otelcol-config.yaml  # OTLP fan-out to Jaeger + Prometheus
│       │   ├── promtail-config.yaml
│       │   └── alerting/alerts.yaml
│       ├── storage/pod-storage.yaml
│       └── edge/                # Optional reverse proxy (local HTTP or CF TLS)
├── scripts/
│   ├── deploy.sh                # Deployment orchestrator (reads profile → deploys pods in order)
│   ├── teardown.sh              # Stops/removes pods for a profile
│   ├── setup-ubuntu.sh          # Installs Podman + fuse3 on Ubuntu
│   ├── bootstrap-openbao.sh     # Initializes OpenBao + AppRole; writes ROLE_ID/SECRET_ID to .env
│   ├── bootstrap-keycloak.sh    # Realm/clients/roles for local OIDC
│   ├── bootstrap-slm.sh         # Register slm-executor when LM Studio is up
│   ├── generate-seal-keys.sh    # Generates RSA key pair for SEAL gateway
│   ├── install-aegis-cli.sh     # Extracts aegis binary from container image → bin/
│   ├── validate-stack.sh        # curl health checks against all service endpoints
│   ├── init-multiple-dbs.sh     # PostgreSQL multi-database init script
│   └── lib/systemd-user.sh      # Sets XDG_RUNTIME_DIR + DBUS_SESSION_BUS_ADDRESS for non-login shells
├── systemd/
│   └── aegis-fuse-daemon.service  # Systemd user service for host-side FUSE daemon (ADR-107)
├── docs/
│   └── LOCAL-OPS.md             # WSL2 browser rule, LLM, JWT smoke, workflow YAML
├── tests/
│   └── test-systemd-user-env.sh   # Unit tests for scripts/lib/systemd-user.sh
├── .github/
│   └── dependabot.yml             # Weekly Docker + Actions dependency updates
└── .markdownlint-cli2.jsonc        # Relaxed markdown linting rules
```

## Pod Architecture

All pods join `aegis-network` (Podman bridge). Internal DNS resolution uses container names (e.g., `aegis-database`, `temporal`, `otelcol`).

| Pod | Key Services | Exposed Ports |
|---|---|---|
| **pod-core** | aegis-runtime | 8088 (HTTP API), 50051 (gRPC), 2049 (NFS), 9091 (metrics) |
| **pod-database** | PostgreSQL 15, postgres-exporter | 5432, 9187 |
| **pod-secrets** | OpenBao | 8200 |
| **pod-temporal** | Temporal 1.23, Temporal UI, aegis-temporal-worker | 7233 (gRPC), 8233 (UI via Caddy basic auth) |
| **pod-iam** | Keycloak 24 | 8180 |
| **pod-seal-gateway** | aegis-seal-gateway | 8089 (HTTP), 50055 (gRPC) |
| **pod-observability** | Jaeger 1.55, Prometheus 2.51, Grafana 10.4, Loki 3.0, Promtail 3.0, otelcol-contrib 0.99 | 16686 (Jaeger), 4317/4318 (OTLP→otelcol), 9090 (Prometheus), 3300 (Grafana), 3100 (Loki) |
| **pod-storage** | SeaweedFS (master, volume, filer, WebDAV) | 9333, 8080, 8888, 7333 |
| **pod-edge** | Caddy (local HTTP reverse-proxy; optional CF TLS) | 80, 443 |
| **host** | FUSE daemon (systemd user service) | 50053 (gRPC, host-only) |

The observability pipeline: services export OTLP traces to **otelcol** (port 4317), which fans out to Jaeger (traces) and Prometheus remote write (metrics).

### Hard rules for agents working this repo

1. **Read `docs/LOCAL-OPS.md` first** — do not re-discover WSL2 / LLM / JWT pitfalls.
2. **WSL2:** Windows browser must use WSL eth0 IP, never `127.0.0.1`.
3. **LLM config** in `aegis-config.yaml`: prefer-local; literal model ids; `default` alias on local provider; disable dead Gemini.
4. **Auth:** Keycloak client credentials (`aegis-runtime` / `aegis-dev-secret`), not `AEGIS_API_TOKEN`.
5. **Profiles** live in `profiles/*.conf` — docs lag; trust the conf files.
6. Low padding. Prefer action over re-scanning the whole tree.

## Deployment Workflows

### First-time Setup

```bash
cp .env.example .env            # fill in required vars (see below)
make setup                      # install Podman + fuse3 on Ubuntu
make deploy                     # deploy default "development" profile
make bootstrap-secrets          # initialize OpenBao; writes ROLE_ID + SECRET_ID to .env
make bootstrap-keycloak         # configure Keycloak realm, clients, roles
make generate-keys              # generate SEAL RSA key pair → generated/seal/
make status                     # verify all pods running
make validate                   # curl health checks against all services
```

### Common Operations

```bash
# Deploy a specific profile
PROFILE=minimal make deploy
PROFILE=full make deploy

# Redeploy a single pod after config change
make redeploy POD=core
make redeploy POD=observability

# Tail logs
make logs POD=core
make logs POD=temporal

# Run aegis CLI inside the runtime container
make aegis CMD="agent list"
make shell                      # bash into aegis-runtime container

# Tear down
make teardown                   # stops active profile's pods
make clean                      # full teardown + prune volumes/networks

# Health checks
make validate
make status
```

### Deployment Internals

`make deploy` runs `scripts/deploy.sh`, which:

1. Sources `.env` and the active profile's `.conf`
2. Ensures `aegis-network` exists
3. Creates `/tmp/aegis-fuse-mounts/` for FUSE mount prefix (ADR-107)
4. Extracts the `aegis` CLI binary from the container image via `install-aegis-cli.sh`
5. Restarts the systemd FUSE daemon to pick up the new binary
6. Iterates `$PODS` in order, running `envsubst < pod-*.yaml | podman play kube --network aegis-network --replace -`
7. After deploying `pod-secrets`, auto-runs `bootstrap-openbao.sh` and re-sources `.env`

## FUSE Daemon (ADR-107)

The FUSE daemon runs on the **host** as a systemd user service, not inside a pod. This is required because rootless Podman containers cannot mount FUSE filesystems internally.

**Binary location**: `~/100monkeys/aegis-deploy/bin/aegis` (extracted at deploy time from the runtime container image — the `bin/` directory is gitignored)

**Service file**: `systemd/aegis-fuse-daemon.service`

**Management**:
```bash
systemctl --user start/stop/restart/status aegis-fuse-daemon
journalctl --user -u aegis-fuse-daemon -f
```

The daemon:
- Connects to `aegis-runtime` gRPC on `127.0.0.1:50051`
- Mounts workspace volumes as FUSE filesystems under `/tmp/aegis-fuse-mounts/`
- Advertises itself to the orchestrator at `http://host.containers.internal:50053`
- All file access goes through the FSAL security boundary (tenant isolation + access policies)

## Environment Variables

Required variables in `.env` (copy from `.env.example`):

| Variable | Required | Description |
|---|---|---|
| `AEGIS_ROOT` | Yes | Absolute path to this repo checkout |
| `GHCR_USERNAME` | Yes | GitHub username for `ghcr.io/100monkeys-ai` |
| `GHCR_TOKEN` | Yes | GitHub PAT with `read:packages` scope |
| `POSTGRES_PASSWORD` | Yes | PostgreSQL password |
| `ZARU_LLM_API_KEY` | Yes | Google Gemini API key |
| `AEGIS_IMAGE_TAG` | Yes | Image tag to deploy (default: `latest`) |
| `TEMPORAL_UI_USER` | Recommended | Temporal UI basic auth username |
| `TEMPORAL_UI_PASSWORD_HASH` | Recommended | bcrypt hash for Temporal UI (generate with `podman exec aegis-zaru-edge-caddy caddy hash-password --plaintext 'yourpassword'`) |
| `KEYCLOAK_ADMIN_PASSWORD` | Recommended | Keycloak admin password (default: `changeme`) |
| `GRAFANA_ADMIN_PASSWORD` | Recommended | Grafana admin password (default: `changeme`) |
| `OPENBAO_ROLE_ID` | Auto | Populated by `make bootstrap-secrets` — do not set manually |
| `OPENBAO_SECRET_ID` | Auto | Populated by `make bootstrap-secrets` — do not set manually |
| `AEGIS_SEAL_PRIVATE_KEY` | Auto | Populated by `make generate-keys` — do not set manually |
| `CLOUDFLARE_API_TOKEN` | Edge only | Required for Caddy automatic TLS via DNS challenge |
| `CONTAINER_SOCK` | Optional | Podman socket path (default: `/run/user/1000/podman/podman.sock`) |

## Pod YAML Conventions

Pod definitions use **Kubernetes-style YAML** consumed by `podman play kube`. Key conventions:

- Environment variables are injected via `envsubst` at deploy time — use `${VAR}` syntax in YAML, not Podman-specific env mechanisms
- Persistent data uses `PersistentVolumeClaim` objects (Podman maps these to named volumes)
- Config files are mounted via `hostPath` volumes pointing into the repo directory
- All pods specify `hostNetwork: false` and join `aegis-network`
- Container names follow `{pod-name}-{service}` convention (e.g., `aegis-core-aegis-runtime`)

When editing pod YAML:
1. Validate with `envsubst < pod-*.yaml | podman play kube --dry-run -` if possible
2. Use `make redeploy POD=<name>` to test changes (not full `make deploy`)
3. Check container names match what scripts reference (e.g., `validate-stack.sh`, Makefile `aegis` target)

## Scripting Conventions

All scripts use `#!/usr/bin/env bash` with `set -euo pipefail`. Key patterns:

- **Non-login shell fix**: Source `scripts/lib/systemd-user.sh` before any `systemctl --user` calls to ensure `XDG_RUNTIME_DIR` and `DBUS_SESSION_BUS_ADDRESS` are set
- **Env loading**: `set -a && source .env && set +a` (exports all sourced vars)
- **Profile loading**: Profile files contain only a `PODS=` assignment
- **envsubst**: Used to inject `.env` variables into pod YAML at deploy time — only variables referenced in the YAML are substituted

## Testing

```bash
bash tests/test-systemd-user-env.sh   # unit tests for systemd-user.sh helper
make validate                          # integration health checks (requires running stack)
```

The unit tests in `tests/` are standalone Bash scripts — no test framework dependency. When adding helpers to `scripts/lib/`, add corresponding tests.

`shellcheck` is the implicit standard for script quality — scripts should be shellcheck-clean.

## Commit Message Style

This repo uses [Conventional Commits](https://www.conventionalcommits.org/):

```
feat(observability): add OpenTelemetry Collector as OTLP fan-out layer
fix: sync bootstrap-openbao.sh from aegis-platform-deployment
docs: update temporal basic auth comment with podman exec hash-password command
config: increase smart alias max_output_tokens to 16384 for Gemini thinking mode
```

Common scopes: `observability`, `core`, `temporal`, `secrets`, `storage`, `edge`, `iam`.

## Things to Know

- **`bin/` is gitignored** — the `aegis` CLI binary is extracted from the container at deploy time; never commit it
- **`generated/` is gitignored** — SEAL key pairs land here; never commit them
- **`local-volumes/` is gitignored** — local Podman volume data; never commit it
- **`.env` is gitignored** — contains secrets; use `.env.example` as the source of truth
- **`make deploy` is idempotent** — `podman play kube --replace` tears down and recreates pods; safe to re-run
- **Bootstrap is one-time** — `bootstrap-openbao.sh` and `bootstrap-keycloak.sh` detect already-initialized state; safe to re-run but only do real work on first run
- **Pod-edge is not in any profile** — deploy it manually for production: `make redeploy POD=edge`
- **Temporal UI uses Caddy basic auth** — the UI itself has no built-in auth; Caddy in the pod proxies it with HTTP basic auth configured via `TEMPORAL_UI_USER`/`TEMPORAL_UI_PASSWORD_HASH`
- **Database connection pooling** — services connect to PgBouncer on port 5433 (transaction mode), not directly to PostgreSQL on 5432
- **OTLP tracing endpoint** — services send traces to `otelcol:4317`; the collector fans out to Jaeger (display) and Prometheus remote write (metrics)

# Local ops runbook (hard-won)

This document captures machine-local deployment facts that are easy to get wrong.
Update it when behavior changes.

## Profiles (source of truth = `profiles/*.conf`)

| Profile | Pods |
|---|---|
| `minimal` | `secrets core` |
| `development` (default) | `database secrets temporal seal-gateway iam core storage observability` |
| `full` | `database secrets storage temporal seal-gateway core observability` (**no iam**) |

`edge` is **not** in any profile. Deploy with:

```bash
make redeploy POD=edge
```

## WSL2 browser access (HARD RULE)

Stack runs **inside WSL2**. Windows browser `http://127.0.0.1:PORT` is **Windows localhost**, not WSL → **connection refused**.

| Client | Correct base |
|---|---|
| curl / tools **inside WSL** | `http://127.0.0.1:PORT` |
| **Windows browser** | `http://$(hostname -I | awk '{print $1}'):PORT` (currently often `172.27.70.12`) |

### Core UI ports (use WSL IP from Windows)

| UI | Port |
|---|---|
| AEGIS health | 8088 `/health` |
| Keycloak | 8180 |
| Temporal UI | 8233 |
| SEAL Gateway | 8089 |
| OpenBao UI | 8200 `/ui/` |
| Grafana | 3300 |
| Prometheus | 9090 |
| Jaeger | 16686 |
| SeaweedFS Filer | 8888 |
| SeaweedFS Master | 9333 |

## LLM configuration

File: `podman/pods/core/aegis-config.yaml`

- **Strategy:** `prefer-local`, `default_provider: lmstudio`
- **LM Studio (host):** `http://127.0.0.1:1234` — server is already ON.
- **From pods:** `http://host.containers.internal:1234/v1` (container `127.0.0.1` is not the host). LM Studio must bind `0.0.0.0` (`lms server start --bind 0.0.0.0`), not `127.0.0.1`.
- **Model:** [prism-ml/bonsai-27b](https://lmstudio.ai/models/prism-ml/bonsai-27b) (`Bonsai-27B-Q1_0` GGUF). Load it in LM Studio, then confirm the API id:
  `curl -s http://127.0.0.1:1234/v1/models`
  If the `id` differs from `prism-ml/bonsai-27b`, update every `model:` field in `aegis-config.yaml`.
- **Aliases on lmstudio:** `default`, `slm`, `smart`, `judge`, `slm-judge` — all point at Bonsai. Built-ins request `default`.
- **Gemini:** `enabled: false` unless `ZARU_LLM_API_KEY` is set.
- After edits: `podman restart aegis-core-aegis-runtime` (config is hostPath-mounted).

**Note:** Small SLMs often fail workflow-generator / creator agents with **context size exceeded**. Simple agent execute and YAML workflow register still work.

## API auth

- `AEGIS_API_TOKEN` is **not** a JWT → `Unauthorized` / `InvalidToken` on `/v1/*`.
- Keycloak **issuer** is `http://127.0.0.1:8180/realms/aegis-system`. Do **not** use `auth.localhost` or `--proxy=edge` without a reverse proxy — that hangs the Admin UI on “Loading the Admin UI”.
- Admin console: <http://127.0.0.1:8180/admin/> (`admin` / `changeme` unless you changed `KEYCLOAK_ADMIN_PASSWORD`).
- Bootstrap (`scripts/bootstrap-keycloak.sh`) creates client `aegis-runtime` with secret **`placeholder`** (not `aegis-dev-secret`).
- Working non-interactive token:

```bash
TOKEN=$(curl -sS -X POST 'http://127.0.0.1:8180/realms/aegis-system/protocol/openid-connect/token' \
  -H 'Content-Type: application/x-www-form-urlencoded' \
  -d 'client_id=aegis-runtime&client_secret=placeholder&grant_type=client_credentials' \
  | python3 -c 'import sys,json;print(json.load(sys.stdin)["access_token"])')
```

Requires `make bootstrap-keycloak` once (idempotent). Re-run after changing scopes. The client needs `agent:list`, `agent:execute`, `agent:deploy`, `execution:read`, `workflow:run`, and related scopes assigned as default client scopes.

## Agent execute vs Temporal workflows

These are **different surfaces**. [docs.100monkeys.ai workflows](https://docs.100monkeys.ai/docs/workflows/building-workflows) are Temporal FSMs. Direct agent execute is in-process on `aegis-runtime`.

| Action | CLI | Shows in Temporal UI (`:8233`, namespace `default`)? |
|---|---|---|
| Spawn an agent | `aegis agent run <name> --intent '...'` | **No** — use `aegis task status` / `task logs` |
| Run a workflow | `aegis workflow run builtin-intent-to-execution --intent '...'` | **Yes** — type `aegis_workflow`, queue `aegis-agents` |

`hello-world` is registered but **cannot start**: its `input_schema` requires top-level `task`, and the runtime validates a wrapped object that does not have `task`. Use `aegis-python-executor-agent` (no schema) for a first spawn:

```bash
AEGIS_KEY="$TOKEN" aegis --host 127.0.0.1 --port 8088 --output json \
  agent run aegis-python-executor-agent \
  --intent 'Write a Python function fib(n) that returns the first n Fibonacci numbers. Save it to /workspace/solution.py and self-test it.'
```

Then:

```bash
AEGIS_KEY="$TOKEN" aegis --host 127.0.0.1 --port 8088 task logs <execution_id> --follow
```

To see work in Temporal:

```bash
AEGIS_KEY="$TOKEN" aegis --host 127.0.0.1 --port 8088 --output json \
  workflow run builtin-intent-to-execution \
  --intent 'Write a Python function fib(n) that returns the first n Fibonacci numbers.' \
  --input '{"language":"python","language_ext":"py","runner":"python3","runner_flags":"-s","container_image":"python:3.11-slim","inputs":{"n":10},"inputs_json":"{\"n\":10}"}'
```

Open <http://127.0.0.1:8233/namespaces/default/workflows> (not `temporal-system`).

Confirm LLM path:

```bash
podman logs --since 5m aegis-core-aegis-runtime 2>&1 | grep -E 'LLM inference|LLM HTTP'
# expect: model=prism-ml/bonsai-27b endpoint=http://host.containers.internal:1234/v1/chat/completions
```

## Register a workflow record (YAML)

`POST /v1/workflows` expects a YAML manifest (`Content-Type: application/yaml`):

```yaml
apiVersion: 100monkeys.ai/v1   # not aegis.ai/v1
kind: Workflow
metadata:
  name: hello-ping
  description: Example one-step workflow
  version: "1.0.0"
spec:
  initial_state: start
  states:
    start:
      kind: Agent
      agent: hello-world
      input: '{"task":"pong"}'   # string, not a map
      transitions:
        - target: end
          condition: always     # enum: always, on_success, on_failure, ...
    end:
      kind: System
      command: "echo done"
      transitions: []
```

List: `GET /v1/workflows`.

CLI alternatives: `aegis workflow deploy <file>`, `aegis workflow generate -i "..."`, `aegis workflow list`.

## Edge (local)

Current `podman/pods/edge/Caddyfile` is **local HTTP** (`auto_https off`) for reverse-proxy to stack services. No Cloudflare token required.

- Grafana backend is **`:3000` inside the pod** (host maps 3300→3000).
- Production TLS: restore `acme_dns cloudflare` + real `DOMAIN_*` + `CLOUDFLARE_API_TOKEN`.

```bash
make redeploy POD=edge
curl -sS http://127.0.0.1/   # → aegis-edge ok (from WSL)
```

## Grafana “Runtime / Keycloak / OpenBao down”

Those panels use Prometheus `up{job=...}`. The processes can be healthy while scrapes fail:

| Job | Real health | Scrape failure | Fix in this repo |
|---|---|---|---|
| `aegis-runtime` | `:8088/health` 200 | Metrics bind `127.0.0.1:9091` | `metrics-proxy` sidecar on **:9092**; Prometheus target `aegis-core:9092` |
| `keycloak` | `:8180/health/ready` 200 | `/metrics` 404 | `--metrics-enabled=true` |
| `openbao` | `/v1/sys/health` 200 | `/v1/sys/metrics` 403 | `unauthenticated_metrics_access` on the **listener** stanza, not only top-level `telemetry` |

Dashboard queries use `max(up{job="..."})` so a stale instance label cannot keep a panel red.

## FUSE daemon

Unit: `~/.config/systemd/user/aegis-fuse-daemon.service`  
Binary: `$REPO/bin/aegis` → `~/.local/bin/aegis` (`ExecStart=%h/.local/bin/aegis`). Not `/usr/local/bin/aegis`.

Cold start: daemon needs orchestrator `:50051`. The unit retries with `StartLimitIntervalSec=0`. After core is up:

```bash
systemctl --user reset-failed aegis-fuse-daemon
systemctl --user restart aegis-fuse-daemon
```

## Host notes (this checkout)

- `make setup` supports **Ubuntu 22.04/24.04 and Kali** (native Podman packages on Kali).
- Infra can come up with **no LLM**. Enable LM Studio when a model is loaded.
- User-local tools used by bootstrap: `~/.local/bin/bao`, `~/.local/bin/jq` (not always on the distro).
- Pod DNS is the **pod** name (`aegis-temporal`, `aegis-observability`), not container names (`temporal`, `otelcol`).
- `AEGIS_OTLP_ENDPOINT=http://aegis-observability:4317`

## Execution timeouts (5 minutes)

Local SLM overlays in `manifests/slow-slm/` set **5 minutes** on every execution layer (right field for each):

| Layer | Field | Value |
|---|---|---|
| LLM generate | `llm_timeout_seconds` / `llm_overall_timeout_secs` | `300` |
| Agent iteration | `iteration_timeout` | `5m` |
| Agent resource wall clock | `security.resources.timeout` | `5m` |
| Workflow state (WRITE/VALIDATE/EXECUTE) | `states.*.timeout` | `5m` |
| Isolated code run | `EXECUTE_CODE.resources.timeout` | `5m` |
| Formatter Temporal activity | `output_handler.timeout_seconds` | `300` |

Overlays are **v1.0.1** so stock **v1.0.0** builtins re-applied on core start stay underneath. Latest = 5 minute timeouts.

A Temporal `Activity task failed` at `EXECUTE_CODE` with 3 iterations is usually the **formatter activity**, not the Python container.

Thinking 27B models may still exceed 5 minutes — disable **Enable Thinking** in LM Studio if needed.

## Known non-blockers

- Cortex missing → WARN "memoryless mode"
- Cold `make deploy` is slow (many image pulls); `install-cli` may run twice
- Early `make validate` can fail while Keycloak/Loki warm up — re-check once
- Temporal UI on host `:8233` has **no** Caddy basic auth in this checkout (vars `TEMPORAL_UI_*` are unused unless edge is deployed)
- `hello-world` agent cannot start (input_schema `task` vs wrapped execute payload)

# Local ops runbook (hard-won)

This document captures machine-local deployment facts that are easy to get wrong.
Update it when behavior changes.

This checkout is **native Linux** (Kali + rootless Podman). `http://127.0.0.1:PORT` is correct on the host. WSL2 notes below apply only if you run the stack inside WSL.

Related:

- Overlay timeouts: [manifests/slow-slm/README.md](../manifests/slow-slm/README.md)
- 2026-08-21 field report (accessible PDF + unified diff): [AEGIS-Local-SLM-Field-Report-2026-08-21.pdf](AEGIS-Local-SLM-Field-Report-2026-08-21.pdf)
- Host I/O / swappiness notes: [pc-tuning/summary.md](../pc-tuning/summary.md)

## Profiles (source of truth = `profiles/*.conf`)

| Profile | Pods |
|---|---|
| `minimal` | `secrets core` |
| `development` (default) | `database secrets temporal seal-gateway iam core mcp storage observability` |
| `full` | `database secrets storage temporal seal-gateway core mcp observability` (**no iam**) |

`edge` is **not** in any profile. Deploy with:

```bash
make redeploy POD=edge
```

## Browser access

| Client | Correct base |
|---|---|
| Native Linux (this checkout) | `http://127.0.0.1:PORT` |
| Tools **inside WSL** | `http://127.0.0.1:PORT` |
| **Windows browser → WSL2 stack** | WSL eth0 IP from `hostname -I` (Windows `127.0.0.1` is **not** WSL) |

### Core UI ports

| UI | Port |
|---|---|
| AEGIS health | 8088 `/health` |
| Keycloak | 8180 |
| Temporal UI | 8233 |
| SEAL Gateway | 8089 |
| Zaru MCP | 8090 `/health`, `/mcp/v1` |
| OpenBao UI | 8200 `/ui/` |
| Grafana | 3300 |
| Prometheus | 9090 |
| Jaeger | 16686 |
| SeaweedFS Filer | 8888 |
| SeaweedFS Master | 9333 |

## LLM configuration

File: `podman/pods/core/aegis-config.yaml`

- **Strategy:** `prefer-local`, `default_provider: lmstudio`
- **LM Studio (host):** bind **`0.0.0.0:1234`** (`lms server start --bind 0.0.0.0`). Infra comes up with no model. `make teardown` does **not** stop LM Studio.
- **From pods:** `http://host.containers.internal:1234/v1` (container `127.0.0.1` is not the host). LM Studio must bind `0.0.0.0` (`lms server start --bind 0.0.0.0`), not `127.0.0.1`.
- **Kali + netavark:** Podman injects `host.containers.internal` → `169.254.1.2`, which **times out** from `aegis-network`. `scripts/patch-host-gateway.sh` rewrites it to the host LAN IPv4 (default-route `src`). `make deploy` / `make redeploy POD=core` run that patch. Verify: `podman exec aegis-core-aegis-runtime curl -sS http://host.containers.internal:1234/v1/models`.
- **Model:** [`qwen2.5-coder-7b-instruct`](https://huggingface.co/lmstudio-community/Qwen2.5-Coder-7B-Instruct-GGUF) (`Q4_K_M`). Confirm id:
  `curl -s http://127.0.0.1:1234/v1/models`
  If the `id` differs, update every `model:` field in `aegis-config.yaml`.
- **Load (GTX 1660 Ti 6GB):** `lms unload --all` then `lms load qwen2.5-coder-7b-instruct --gpu max -c 4096 --parallel 1 -y`. Thinking **off**.
- **Aliases on lmstudio:** `default`, `slm`, `smart`, `judge`, `slm-judge` — all point at Qwen Coder 7B. Built-ins request `default`. `max_output_tokens` is 2048 (1024 for judge), not 8192.
- **Gemini:** `enabled: false` unless `ZARU_LLM_API_KEY` is set.
- After config edits: `podman restart aegis-core-aegis-runtime` (config is hostPath-mounted), then **`make overlays`** — core start re-registers stock **v1.0.0** builtins.

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

Requires `make bootstrap-keycloak` once (idempotent). Re-run after changing scopes. The client needs `agent:list`, `agent:execute`, `agent:deploy`, `execution:read`, `workflow:run`, `workflow:logs` (required for `aegis workflow run --follow`), and related scopes assigned as default client scopes.

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
  --input '{"language":"python","language_ext":"py","runner":"python3","runner_flags":"-s","container_image":"python:3.11-slim","inputs":{"n":10},"inputs_json":"{\"n\":10}"}' \
  --follow
```

`--follow` needs the `workflow:logs` client scope. Do **not** pin workflow version `1.0.0` — that is the stock builtin; latest is the slow-SLM overlay (**1.0.4**).

Open <http://127.0.0.1:8233/namespaces/default/workflows> (not `temporal-system`).

Confirm LLM path:

```bash
podman logs --since 5m aegis-core-aegis-runtime 2>&1 | grep -E 'LLM inference|LLM HTTP'
# expect: model=qwen2.5-coder-7b-instruct endpoint=http://host.containers.internal:1234/v1/chat/completions
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

## Zaru MCP server ([aegis-mcp-tools](https://github.com/100monkeys-ai/aegis-mcp-tools))

Pod `aegis-mcp` runs `ghcr.io/100monkeys-ai/zaru-mcp-server`. It does **not** implement tools itself: it lists `/v1/seal/tools` on the orchestrator and wraps every `tools/call` in a SEAL envelope (`POST /v1/seal/attest` + `/v1/seal/invoke`).

| | |
|---|---|
| Health | http://127.0.0.1:8090/health |
| MCP (StreamableHTTP) | http://127.0.0.1:8090/mcp/v1 |
| SSE (legacy) | http://127.0.0.1:8090/mcp/v1/sse |
| Local auth | `BYPASS_AUTH=true` — a Bearer token is still **required**, any string works |
| JWKS (when bypass is off) | `http://aegis-iam:8180/realms/aegis-system/...` — JWT `iss` is `http://127.0.0.1:8180`, so real JWT auth from inside the pod needs a hostname fix; use bypass or a Keycloak JWT from the host |

```bash
# health
curl -sS http://127.0.0.1:8090/health

# MCP client (Claude Code)
claude mcp add zaru --transport http http://127.0.0.1:8090/mcp/v1 \
  --header "Authorization: Bearer $TOKEN"
```

Local tools on the MCP server (not forwarded): `zaru.init`, `zaru.mode`. Everything else is AEGIS tools via SEAL.

Docs: https://docs.100monkeys.ai/docs/zaru/mcp-client-setup

## Execution timeouts (slow SLM)

Local SLM overlays in `manifests/slow-slm/`: writers **v1.0.2**, formatter **v1.0.3**, workflow **v1.0.4**. A 5-minute **overall** agent budget is not enough for VALIDATE_CODE: that agent must `fs.read` then emit JSON, and a thinking 27B can spend the entire 300s on the first generate (`Execution timed out after 300 seconds` at `final_state: VALIDATE_CODE`).

| Layer | Field | Writer | Validator |
|---|---|---|---|
| LLM generate | `llm_timeout_seconds` | `300` | `600` |
| Orchestrator LLM HTTP client | `llm_overall_timeout_secs` | `180` | `180` |
| Agent iteration | `iteration_timeout` | `5m` | `10m` |
| Agent run wall clock | `security.resources.timeout` | `15m` | `20m` |
| Workflow state | `states.*.timeout` | WRITE/VALIDATE/EXECUTE `5m` | same |
| Isolated code run | `EXECUTE_CODE.resources.timeout` | `5m` | n/a |
| Formatter Temporal activity | `output_handler.timeout_seconds` | `15` (`required: false`) | n/a |

`make deploy` and `make redeploy POD=core` apply overlays after core is healthy. `make overlays` is the standalone re-apply. Core start re-registers stock **v1.0.0** builtins; overlay versions stay latest.

A Temporal `Activity task failed` at `EXECUTE_CODE` with 3 iterations is usually the **formatter activity**, not the Python container. Overlay 1.0.4 makes the formatter optional so a slow format cannot fail a successful container run.

Disable **Enable Thinking** in LM Studio if a single generate still stalls past 10 minutes.

## Teardown

```bash
make teardown          # development-profile pods + FUSE daemon
```

Does **not**:

- Stop LM Studio (`lms unload --all`; stop the server separately if you want GPU RAM back)
- Remove leftover isolated execution containers (`aegis-agent-*`). `AEGIS_KEEP_CONTAINER=false` still left a `python:3.11-slim` `tail -f /dev/null` container after a long session.

After teardown, `podman pod ps` should be empty. Sweep leftovers:

```bash
podman ps -a --filter name=aegis-agent-
podman rm -f $(podman ps -aq --filter name=aegis-agent-)
```

## Known non-blockers

- Cortex missing → WARN "memoryless mode"
- Cold `make deploy` is slow (many image pulls); `install-cli` may run twice
- Early `make validate` can fail while Keycloak/Loki warm up — re-check once
- Temporal UI on host `:8233` has **no** Caddy basic auth in this checkout (vars `TEMPORAL_UI_*` are unused unless edge is deployed)
- `hello-world` agent cannot start (input_schema `task` vs wrapped execute payload)
- Isolated `aegis-agent-*` containers can outlive `make teardown` — see Teardown
- Grafana / Keycloak / OpenBao “down” in dashboards is often scrape config, not process death (table above)

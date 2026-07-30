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
- **LM Studio:** OpenAI-compat endpoint (set to your host; this checkout uses Tailscale `http://100.94.83.101:1234/v1`)
- **Model id:** use a **literal** model name (e.g. `liquid/lfm2.5-1.2b`). `env:LM_STUDIO_MODEL` is **not** expanded for the model field.
- **Aliases on lmstudio:** `default`, `slm`, `smart`, `judge`, `slm-judge` — all must exist on the local provider. Built-ins request `default`; if only Gemini has it, traffic goes cloud.
- **Gemini:** disable when prepaid/quota is dead (`enabled: false`) so the stack does not 429-loop.
- After edits: `podman restart aegis-core-aegis-runtime` (config is hostPath-mounted).

**Note:** Small SLMs often fail workflow-generator / creator agents with **context size exceeded**. Simple agent execute and YAML workflow register still work.

## API auth

- `AEGIS_API_TOKEN` is **not** a JWT → `Unauthorized` / `InvalidToken` on `/v1/*`.
- Working non-interactive token:

```bash
TOKEN=$(curl -sS -X POST 'http://localhost:8180/realms/aegis-system/protocol/openid-connect/token' \
  -H 'Content-Type: application/x-www-form-urlencoded' \
  -d 'client_id=aegis-runtime&client_secret=aegis-dev-secret&grant_type=client_credentials' \
  | python3 -c 'import sys,json;print(json.load(sys.stdin)["access_token"])')
```

Requires `make bootstrap-keycloak` once (idempotent).

## Smoke: agent execute

```bash
# list agents
curl -sS -H "Authorization: Bearer $TOKEN" http://127.0.0.1:8088/v1/agents

# execute (example: slm-executor)
EID=$(curl -sS -X POST -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' \
  -d '{"input":{"task":"write def add(a,b): return a+b"}}' \
  http://127.0.0.1:8088/v1/agents/<AGENT_ID>/execute \
  | python3 -c 'import sys,json;print(json.load(sys.stdin)["execution_id"])')

# poll
curl -sS -H "Authorization: Bearer $TOKEN" http://127.0.0.1:8088/v1/executions/$EID
```

Confirm LLM path in logs:

```bash
podman logs --since 5m aegis-core-aegis-runtime 2>&1 | grep -E 'LLM inference|LLM HTTP'
# expect: provider=openai endpoint ...:1234/v1/chat/completions status=200
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

## Known non-blockers

- Cortex missing → WARN "memoryless mode"
- Cold `make deploy` is slow (many image pulls); `install-cli` may run twice
- Early `make validate` can fail while Keycloak warms up — re-check once

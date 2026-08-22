# Local SLM timeouts

Stock builtins use one 5-minute budget for the **entire** agent run. That is not enough for a thinking 27B: VALIDATE_CODE must `fs.read` then emit JSON (two LLM generates). A single generate can consume the whole 300s wall clock (`overall_timeout_secs=300`) and the workflow fails at VALIDATE with `Execution timed out after 300 seconds`.

Overlays split the knobs:

| Context | Field | Writer / formatter | Validator |
|---|---|---|---|
| Single LLM HTTP generate | `spec.execution.llm_timeout_seconds` | `300` | `600` |
| One agent iteration | `spec.execution.iteration_timeout` | `5m` | `10m` |
| Agent run wall clock (`overall_timeout_secs`) | `spec.security.resources.timeout` | `15m` | `20m` |
| Orchestrator LLM HTTP client | `llm_selection.llm_overall_timeout_secs` in `aegis-config.yaml` | `180` | `180` |
| Workflow Agent/ContainerRun **state** | `spec.states.*.timeout` | WRITE/VALIDATE/EXECUTE `5m` | same |
| Isolated code container | `EXECUTE_CODE.resources.timeout` | `5m` | n/a |
| Formatter agent wall clock | `aegis-output-formatter-agent` `resources.timeout` | `10m` | n/a |
| Temporal output-handler activity | `output_handler.timeout_seconds` | `15` (`required: false`) | n/a |

Not changed: OTLP exporter `5s`, health probes, Prometheus scrapes, TCP checks in `validate-stack.sh`.

```bash
make overlays
```

Equivalent:

```bash
TOKEN=$(curl -sS -X POST 'http://127.0.0.1:8180/realms/aegis-system/protocol/openid-connect/token' \
  -H 'Content-Type: application/x-www-form-urlencoded' \
  -d 'client_id=aegis-runtime&client_secret=placeholder&grant_type=client_credentials' \
  | python3 -c 'import sys,json; print(json.load(sys.stdin)["access_token"])')
export AEGIS_KEY="$TOKEN"

for f in manifests/slow-slm/aegis-*-agent.yaml; do
  aegis --host 127.0.0.1 --port 8088 agent deploy --force "$f"
done
aegis --host 127.0.0.1 --port 8088 workflow deploy --force --scope global \
  manifests/slow-slm/builtin-intent-to-execution.yaml
```

Overlay versions stay above stock **1.0.0** so a core restart that re-deploys builtins does not become latest: writers **1.0.2**, formatter **1.0.3**, workflow **1.0.4**. `aegis workflow run` / `aegis.execute.intent` use latest. `make deploy` and `make redeploy POD=core` apply these overlays after core is healthy; `make overlays` re-applies them on demand.

Disable **Enable Thinking** in LM Studio if a single generate still stalls past 10 minutes.

Do **not** pin `aegis workflow run ... --version 1.0.0`. Stock builtins are 1.0.0; the overlay versions above are what `latest` should resolve to after `make overlays`.

# Local SLM timeouts (5 minutes)

All **execution** timeouts in this directory are **5 minutes**, using the field that matches each layer:

| Context | Field | Value |
|---|---|---|
| Single LLM HTTP generate | `spec.execution.llm_timeout_seconds` | `300` |
| One agent iteration | `spec.execution.iteration_timeout` | `5m` |
| Agent container / FSAL wall clock | `spec.security.resources.timeout` | `5m` |
| Orchestrator-wide LLM generate | `llm_selection.llm_overall_timeout_secs` in `aegis-config.yaml` | `300` |
| Workflow Agent/ContainerRun **state** | `spec.states.*.timeout` | `5m` |
| Isolated code container | `EXECUTE_CODE.resources.timeout` | `5m` |
| Temporal output-handler activity | `output_handler.timeout_seconds` | `300` |

Not changed: OTLP exporter `5s`, health probes, Prometheus scrapes, TCP checks in `validate-stack.sh`.

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

Overlays use **version 1.0.1** so a core restart that re-deploys stock **1.0.0** builtins does not become latest. `aegis workflow run` / agent execute use latest.

A thinking 27B may still exceed 5 minutes; disable **Enable Thinking** in LM Studio if generate calls stall.

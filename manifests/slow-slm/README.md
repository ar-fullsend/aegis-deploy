# Slow local SLM timeouts

Builtin executors used by `builtin-intent-to-execution` (`WRITE_CODE`) ship with `resources.timeout: 300s` and `llm_timeout_seconds: 120`. A local 27B thinking model (Bonsai) often spends the whole budget on `reasoning_content` and never finishes a tool call.

This directory re-deploys those builtins with:

- `llm_timeout_seconds: 1800` (30 minutes per LLM call)
- `iteration_timeout: 45m`
- `resources.timeout: 30m`

```bash
TOKEN=$(curl -sS -X POST 'http://127.0.0.1:8180/realms/aegis-system/protocol/openid-connect/token' \
  -H 'Content-Type: application/x-www-form-urlencoded' \
  -d 'client_id=aegis-runtime&client_secret=placeholder&grant_type=client_credentials' \
  | python3 -c 'import sys,json; print(json.load(sys.stdin)["access_token"])')
export AEGIS_KEY="$TOKEN"

for f in manifests/slow-slm/aegis-*-agent.yaml; do
  aegis --host 127.0.0.1 --port 8088 agent deploy --force "$f"
done
```

The pipeline’s `EXECUTE_CODE` **output_handler** still had `timeout_seconds: 60` (Temporal activity). Bonsai times out there even after the formatter agent itself is patched. `builtin-intent-to-execution.yaml` sets that to **1800**.

```bash
aegis --host 127.0.0.1 --port 8088 workflow deploy --force --scope global \
  manifests/slow-slm/builtin-intent-to-execution.yaml
```

Do **not** set `AEGIS_FORCE_DEPLOY_BUILTINS=true` afterward — that restores stock 60s/300s builtins.

Faster option: in LM Studio turn **Enable Thinking** off for Bonsai so the model emits `content` instead of a long `reasoning_content` preamble.

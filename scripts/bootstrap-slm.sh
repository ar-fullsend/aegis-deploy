#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(dirname "$SCRIPT_DIR")"

if [[ -f "$ROOT_DIR/.env" ]]; then
    set -a
    source "$ROOT_DIR/.env"
    set +a
fi

RUNTIME_URL="http://localhost:8088"
KEYCLOAK_URL="${KEYCLOAK_URL:-http://localhost:8180}"
LM_STUDIO_URL="http://${LM_STUDIO_HOST:-localhost:1234}"
SLM_MODEL="${LM_STUDIO_MODEL:-phi-3-mini-4k-instruct}"

echo "==> Bootstrapping SLM subworkflow agent (model: $SLM_MODEL via LM Studio)"

# Check LM Studio is reachable
echo "Checking LM Studio at $LM_STUDIO_URL..."
if ! curl -sf --max-time 5 "$LM_STUDIO_URL/v1/models" > /dev/null 2>&1; then
    echo "ERROR: LM Studio not reachable at $LM_STUDIO_URL"
    echo "  Make sure LM Studio is running and the local server is started."
    exit 1
fi
echo "LM Studio is up."

# Get runtime auth token
echo "Getting auth token..."
TOKEN=$(curl -s -X POST "$KEYCLOAK_URL/realms/aegis-system/protocol/openid-connect/token" \
    -H "Content-Type: application/x-www-form-urlencoded" \
    -d "client_id=aegis-runtime&client_secret=placeholder&grant_type=client_credentials" | \
    python3 -c "import sys,json; print(json.load(sys.stdin)['access_token'])")

if [[ -z "$TOKEN" || "$TOKEN" == "null" ]]; then
    echo "ERROR: Could not get auth token."
    exit 1
fi

# Register the SLM subworkflow agent
echo "Registering slm-executor agent..."
RESPONSE=$(curl -s -w "\n%{http_code}" -X POST "$RUNTIME_URL/v1/agents" \
    -H "Authorization: Bearer $TOKEN" \
    -H "Content-Type: application/json" \
    -d '{
        "apiVersion": "100monkeys.ai/v1",
        "kind": "Agent",
        "metadata": {
            "name": "slm-executor",
            "version": "1.0.0",
            "description": "Executes tasks using a local SLM via LM Studio. Writes and tests Python code without any cloud LLM calls.",
            "scope": "global",
            "labels": {
                "provider": "lmstudio",
                "category": "demo",
                "role": "worker"
            }
        },
        "spec": {
            "input": {
                "schema": {
                    "type": "object",
                    "properties": {
                        "task": {
                            "type": "string",
                            "description": "Description of the Python function or program to write"
                        }
                    },
                    "required": ["task"]
                }
            },
            "runtime": {
                "language": "python",
                "version": "3.11"
            },
            "task": {
                "instruction": "Write a Python function that fulfills the user task description. Include a simple self-test at the bottom of the file using assert statements to verify the function works correctly."
            },
            "model_alias": "slm",
            "judge_model_alias": "slm-judge",
            "system_prompt": "You are a Python code generation assistant running on a local SLM. Write concise, correct Python functions based on the user task. Include a simple test at the bottom of the file to verify the function works.",
            "execution": {
                "timeout_seconds": 300,
                "max_retries": 2,
                "validation": [
                    {
                        "type": "multi_judge",
                        "judges": ["code-quality-judge"],
                        "criteria": "Code is correct, readable, and handles edge cases.",
                        "threshold": 0.7
                    }
                ]
            }
        }
    }')

HTTP_CODE=$(echo "$RESPONSE" | tail -1)
BODY=$(echo "$RESPONSE" | head -1)

if [[ "$HTTP_CODE" == "200" || "$HTTP_CODE" == "201" ]]; then
    AGENT_ID=$(echo "$BODY" | python3 -c "import sys,json; print(json.load(sys.stdin).get('id','unknown'))")
    echo "Agent registered: slm-executor (id: $AGENT_ID)"
else
    echo "Warning: Agent registration returned HTTP $HTTP_CODE: $BODY"
    echo "(Agent may already exist — check with: make aegis CMD='agent list')"
fi

echo ""
echo "==> SLM bootstrap complete"
echo ""
echo "Run the SLM agent:"
echo "  TOKEN=\$(curl -s -X POST \"$KEYCLOAK_URL/realms/aegis-system/protocol/openid-connect/token\" \\"
echo "    -H \"Content-Type: application/x-www-form-urlencoded\" \\"
echo "    -d \"client_id=aegis-runtime&client_secret=placeholder&grant_type=client_credentials\" | python3 -c \"import sys,json; print(json.load(sys.stdin)['access_token'])\")"
echo ""
echo "  AGENT_ID=\$(curl -s -H \"Authorization: Bearer \$TOKEN\" \"$RUNTIME_URL/v1/agents\" | python3 -c \"import sys,json; agents=[a for a in json.load(sys.stdin) if a['name']=='slm-executor']; print(agents[0]['id'] if agents else 'not found')\")"
echo ""
echo "  curl -s -X POST \"$RUNTIME_URL/v1/agents/\$AGENT_ID/execute\" \\"
echo "    -H \"Authorization: Bearer \$TOKEN\" \\"
echo "    -H \"Content-Type: application/json\" \\"
echo "    -d '{\"input\": \"write a function that checks if a number is prime\"}'"

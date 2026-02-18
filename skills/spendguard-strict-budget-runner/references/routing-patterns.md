# Routing Patterns

## OpenAI Python SDK via SpendGuard

```python
import os
from openai import OpenAI

agent_id = os.environ["SPENDGUARD_AGENT_ID"]

client = OpenAI(
    base_url="http://127.0.0.1:8787/v1",
    api_key="not-used-in-sidecar-mode",
)

resp = client.chat.completions.create(
    model="gpt-4o-mini",
    messages=[{"role": "user", "content": "Say hello"}],
    extra_headers={"x-cynsta-agent-id": agent_id},
)
print(resp.choices[0].message.content)
```

## Direct HTTP (OpenAI-compatible route)

```bash
curl -X POST http://127.0.0.1:8787/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "x-cynsta-agent-id: <agent_id>" \
  -d '{
    "model": "gpt-4o-mini",
    "messages": [{"role": "user", "content": "hello"}],
    "max_tokens": 64
  }'
```

## Direct HTTP (explicit run route)

```bash
curl -X POST http://127.0.0.1:8787/v1/agents/<agent_id>/runs/<run_id>/openai/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "gpt-4o-mini",
    "messages": [{"role": "user", "content": "hello"}],
    "max_tokens": 64
  }'
```

## Notes

- Send requests to SpendGuard routes, not provider base URLs.
- Keep one `agent_id` per strict budget scope.
- Generate `run_id` via `POST /v1/agents/{agent_id}/runs` when explicit run tracking is needed.

# Quickstart: Local Sidecar in Minutes

This guide gets you running with:
- local `spendguard-sidecar`
- remote signed pricing from Cynsta cloud
- CLI (`cynsta-spendguard`) for create/list/budget checks

## Prerequisites

- Docker Desktop (or Docker Engine + Compose v2)
- Python 3.10+ (for CLI usage)
- Internet access (to fetch pricing from cloud)

## 1) Start Local Sidecar (Docker, Recommended)

Open a terminal in `spendguard-sidecar`:

```powershell
cd spendguard-sidecar
Copy-Item .env.example .env
# Edit .env and set provider keys you plan to use.

docker compose up -d --build
docker compose logs -f sidecar
```

Expected: service starts successfully and does not fail pricing signature verification.

## Optional: Start Sidecar From Source (No Docker)

If you prefer a direct Python run:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt

$env:CAP_MODE = "sidecar"
$env:CAP_STORE = "sqlite"
$env:CAP_SQLITE_PATH = ".\\cynsta-spendguard.db"
$env:CAP_PRICING_SOURCE = "remote"
$env:CAP_PRICING_URL = "https://api.cynsta.com/v1/public/pricing"
$env:CAP_PRICING_VERIFY_SIGNATURE = "true"
$env:CAP_PRICING_SCHEMA_VERSION = "1"

uvicorn app.main:app --reload --port 8787
```

## 2) Verify Sidecar Health

In a new terminal:

```powershell
Invoke-WebRequest -UseBasicParsing http://127.0.0.1:8787/health
```

Expected response body contains:

```json
{"status":"ok"}
```

## 3) Install CLI and Point to Local Sidecar

```powershell
python -m pip install --upgrade pip
python -m pip install cynsta-spendguard

$env:CAP_BASE_URL = "http://127.0.0.1:8787"
```

If you are developing the SDK locally, use editable install instead:

```powershell
cd ../spendguard-sdk
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e .
```

## 4) Create Agent and Budget

```powershell
spendguard agent create --name "agent-1"
spendguard agent list

# Replace with the returned agent_id:
spendguard budget set --agent <agent_id> --limit 5000 --topup 500
spendguard budget get --agent <agent_id>
```

If these commands work, local onboarding is complete.

## 5) Wire It Into Your Agent Code

After creating a budget, your app must send model calls through sidecar and include the SpendGuard agent id.

Key requirement:
- send requests to sidecar (`http://127.0.0.1:8787/v1/...`), not directly to provider APIs
- include header `x-cynsta-agent-id: <agent_id>`

Example with OpenAI Python SDK:

```python
import os
from openai import OpenAI

agent_id = os.environ["SPENDGUARD_AGENT_ID"]  # set this per running instance/job

client = OpenAI(
    base_url="http://127.0.0.1:8787/v1",
    api_key="not-used-in-sidecar-mode",
)

resp = client.chat.completions.create(
    model="gpt-4o-mini",
    messages=[{"role": "user", "content": "Hello"}],
    extra_headers={"x-cynsta-agent-id": agent_id},
)

print(resp.choices[0].message.content)
```

If you run many instances in parallel:
- use one `SPENDGUARD_AGENT_ID` per instance if each should have separate budget
- or reuse one id for shared budget (current sidecar lock model allows one in-flight run per agent id)

## Optional: Python Client Check

```python
from spendguard_sdk import SpendGuardClient

client = SpendGuardClient("http://127.0.0.1:8787")
agent = client.create_agent("agent-2")
print(agent["agent_id"])
```

## Troubleshooting

`Remote pricing signature verification failed`
- Make sure `CAP_PRICING_VERIFY_SIGNATURE` is `"true"`.
- Ensure `CAP_PRICING_URL` points to the official pricing endpoint.
- If testing non-official cloud, set `CAP_PRICING_SIGNING_PUBLIC_KEY` override.

`Remote pricing request failed`
- Verify `CAP_PRICING_URL` is reachable from your machine.
- Check cloud endpoint directly:
  `Invoke-WebRequest -UseBasicParsing https://api.cynsta.com/v1/public/pricing`

`CLI cannot connect to sidecar`
- Ensure sidecar is running on `127.0.0.1:8787`.
- Confirm `CAP_BASE_URL=http://127.0.0.1:8787`.
- If running with Docker, inspect logs with `docker compose logs sidecar`.

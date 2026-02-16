# Quickstart: Local Sidecar in Minutes

This guide gets you running with:
- local `spendguard-sidecar`
- remote signed pricing from Cynsta cloud
- CLI (`cynsta-spendguard`) for create/list/budget checks

## Prerequisites

- Python 3.10+
- Internet access (to fetch pricing from cloud)

## 1) Start Local Sidecar

Open a terminal in `spendguard-sidecar`:

```powershell
cd spendguard-sidecar
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt

$env:CAP_MODE = "sidecar"
$env:CAP_STORE = "sqlite"
$env:CAP_SQLITE_PATH = ".\\cynsta-spendguard.db"
$env:CAP_PRICING_SOURCE = "remote"
$env:CAP_PRICING_URL = "https://cynsta-spendguard.onrender.com/v1/public/pricing"
$env:CAP_PRICING_VERIFY_SIGNATURE = "true"
$env:CAP_PRICING_SCHEMA_VERSION = "1"

uvicorn app.main:app --reload --port 8787
```

Expected: service starts successfully and does not fail pricing signature verification.

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
cd ../spendguard-sdk
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e .

$env:CAP_BASE_URL = "http://127.0.0.1:8787"
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
  `Invoke-WebRequest -UseBasicParsing https://cynsta-spendguard.onrender.com/v1/public/pricing`

`CLI cannot connect to sidecar`
- Ensure sidecar is running on `127.0.0.1:8787`.
- Confirm `CAP_BASE_URL=http://127.0.0.1:8787`.

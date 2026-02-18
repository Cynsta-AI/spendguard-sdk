# Strict Budget Quickstart

## 1) Start Sidecar

Run in `spendguard-sidecar`:

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

$env:OPENAI_API_KEY = "sk-..."
$env:XAI_API_KEY = "xai-..."
$env:ANTHROPIC_API_KEY = "sk-ant-..."
$env:GEMINI_API_KEY = "..."

uvicorn app.main:app --reload --port 8787
```

## 2) Install and Target CLI

Run in `spendguard-sdk`:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e .
$env:CAP_BASE_URL = "http://127.0.0.1:8787"
```

## 3) Create Agent and Strict Budget

```powershell
spendguard agent create --name "agent-1"
spendguard budget set --agent <agent_id> --limit 5000 --topup 5000
spendguard budget get --agent <agent_id>
```

## 4) Health Check

```powershell
Invoke-WebRequest -UseBasicParsing http://127.0.0.1:8787/health
```

Expected body:

```json
{"status":"ok"}
```

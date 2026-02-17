# SpendGuard SDK

Public SpendGuard repository for:

- Python CLI package (`cynsta-spendguard`)
- Python client library (`spendguard_sdk`)
- API contracts (`contracts/`)
- Public examples and docs

Supported provider endpoint families: `openai`, `grok` (xAI), `gemini`, `anthropic`.

## Install

```bash
pip install cynsta-spendguard
```

or with uv:

```bash
uv tool install cynsta-spendguard
```

## Quickstart

For fast local onboarding with `spendguard-sidecar`, follow [`docs/quickstart.md`](docs/quickstart.md).

## Usage

Create an agent:

```bash
spendguard agent create --name "agent-1"
```

List agents:

```bash
spendguard agent list
```

Set a budget for an existing agent:

```bash
spendguard budget set --agent <agent_id> --limit 5000 --topup 5000
```

Get current budget:

```bash
spendguard budget get --agent <agent_id>
```

Key behavior:

- `CAP_MODE=sidecar` (default): no `x-api-key` is required.
- `CAP_MODE=hosted`: API key is required via `--api-key` or `CAP_API_KEY`.

## Release

Build locally:

```bash
python -m pip install --upgrade build twine
python -m build .
python -m twine check dist/*
```

Publish:

1. Set GitHub secret `PYPI_API_TOKEN`.
2. Push tag `spendguard-cli-vX.Y.Z` (example `spendguard-cli-v0.1.0`).
3. GitHub Actions workflow `.github/workflows/publish-spendguard-cli.yml` publishes to PyPI.

Maintainer setup checklist: `docs/maintainer-setup.md`.

## Python Client

```python
from spendguard_sdk import SpendGuardClient

client = SpendGuardClient("https://spendguard.example.com", api_key="sk_cynsta_live_...")
agent = client.create_agent("agent-1")
client.set_budget(agent["agent_id"], hard_limit_cents=5000, topup_cents=5000)
run = client.create_run(agent["agent_id"])
resp = client.grok_responses(
    agent["agent_id"],
    run["run_id"],
    {"model": "grok-3", "input": "Give me a one-line summary of finite-state machines."},
)
```

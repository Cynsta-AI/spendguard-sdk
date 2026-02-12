# Quickstart

Install:

```bash
pip install cynsta-spendguard
```

Create and budget an agent:

```bash
spendguard agent create --name "agent-1"
spendguard budget set --agent <agent_id> --limit 5000 --topup 5000
spendguard budget get --agent <agent_id>
```

Python client:

```python
from spendguard_sdk import SpendGuardClient

client = SpendGuardClient("https://spendguard.example.com", api_key="sk_cynsta_live_...")
agent = client.create_agent("agent-1")
print(agent["agent_id"])
```

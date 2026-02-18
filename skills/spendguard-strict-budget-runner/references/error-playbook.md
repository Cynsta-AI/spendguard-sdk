# Error Playbook

## `402 Insufficient budget`

Cause:
- `wcec_cents` preflight reserve exceeds `remaining_cents`.

Action:
1. Check current budget:
   - `spendguard budget get --agent <agent_id>`
2. Top up or increase hard limit:
   - `spendguard budget set --agent <agent_id> --limit <new_limit> --topup <topup>`
3. Reduce request size:
   - lower `max_tokens` or prompt size.

## `409 Agent budget is locked by an in-flight run`

Cause:
- Same agent has an active lock from another run.

Action:
1. Reuse same run flow until it settles, or
2. Wait for lock expiry, or
3. Use a different agent ID for concurrent isolated workloads.

## `400 Missing x-cynsta-agent-id header`

Cause:
- Calling `/v1/chat/completions` without required header.

Action:
- Add `x-cynsta-agent-id: <agent_id>` or use explicit `/v1/agents/{agent_id}/runs/{run_id}/...` route.

## `Unknown model for pricing: provider:model`

Cause:
- Model is not in loaded pricing table.

Action:
1. Use supported model ID from active pricing table.
2. Verify sidecar can fetch remote pricing.
3. In cloud-managed environments, ensure pricing document includes the model.

## `Remote pricing signature verification failed`

Cause:
- Invalid signature, wrong public key override, or tampered payload.

Action:
1. Keep `CAP_PRICING_VERIFY_SIGNATURE=true`.
2. Verify `CAP_PRICING_URL` points to trusted cloud endpoint.
3. If using custom cloud, set matching `CAP_PRICING_SIGNING_PUBLIC_KEY`.

## Hosted mode CLI auth errors

Cause:
- Running with `CAP_MODE=hosted` without API key.

Action:
- Pass `--api-key <key>` or set `CAP_API_KEY`.

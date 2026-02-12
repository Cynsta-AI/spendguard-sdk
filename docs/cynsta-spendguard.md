# Cynsta SpendGuard: Research, Decisions, and Implementation Context

**Date:** 2026-02-09
**Status:** Working Notes (MVP implemented)

## 1. Problem Statement

We want a product that lets developers set a **hard spend budget** per agent (for example `$50`), and then:

- route LLM interactions through Cynsta-controlled accounting
- estimate cost before execution (reserve)
- automatically cap output tokens as budgets run low
- prevent overruns (reject or terminate)
- capture real agent traffic (prompts/responses/tool envelopes + usage/cost metadata) to train Cynsta semantic/statistical models

This is distinct from Cynsta Witness’s core “observer” posture, because hard spend enforcement requires being **in the request path** for LLM calls.

## 2. Research Basis

Primary research doc: `docs/cynsta-cap-research.md`.

Long-form/raw notes: `docs/cynsta-spendguard-research.md`.

Key takeaway: 2026-era billing is not reliably “tokens in/out” anymore. Costs can depend on:

- provider-specific usage fields (cached vs uncached tokens, reasoning/thought tokens)
- context threshold cliffs (notably Anthropic 200k tier changes)
- tool/grounding loops (web search calls, grounding query counts)

Therefore, hard caps require a “Financial Governance Middleware” pattern:

1. **Preflight**: estimate worst-case execution cost (WCEC) and reserve funds
2. **Execution**: stream/monitor and enforce caps (max tokens + cancellation)
3. **Settlement**: compute realized cost from provider usage and reconcile reservations

## 3. Core Product Decisions

### 3.1 Two Deployment Variants (to avoid “hosted + BYOK weirdness”)

We ship two versions with shared core logic:

1. **Customer-sidecar (BYOK)**:
   - runs in customer infra
   - customer uses their provider keys
   - Cynsta is not in the critical path (better enterprise fit)

2. **Cynsta-hosted gateway (Cynsta credits)**:
   - runs in Cynsta infra
   - users pay Cynsta prepaid credits
   - Cynsta holds provider keys
   - strongest enforcement + best data capture

### 3.2 Training Data Defaults

- Hosted credits: default allows content capture and training (policy-driven per account; see future legal/ToS work).
- Sidecar: default should be opt-in for full content capture; hashes-only is the safe default.

### 3.3 Enforcement Mode (Hard Cap)

MVP enforces “hard cap” by:

- computing a conservative preflight estimate
- clamping `max_tokens` to affordable output given remaining budget
- rejecting calls when remaining budget cannot cover input + minimum output

Future iteration adds streaming mid-generation cancellation for truly runaway cases.

## 4. Compatibility With Cynsta Witness Architecture

Witness spec (`docs/Cynsta_Forensic_Evidence_Layer.md`, dated 2026-01-20) explicitly rejected a Cynsta-hosted proxy for MVP due to latency/availability risk.

This cap product is compatible by positioning:

- sidecar as the enterprise-default (Cynsta is not in-path to providers)
- hosted credits as a separate offering where customers accept Cynsta being gatekeeper

Both variants can still emit OTEL evidence into the existing ingest pipeline.

## 5. MVP Implementation (What Exists In Repo)

### 5.1 Service

New FastAPI app: `apps/cynsta-spendguard`.

It supports:

- agent creation
- budget create/top-up
- run creation (UUID)
- OpenAI chat completions (non-stream) with enforced `max_tokens` cap
- Gemini generateContent (non-stream) with enforced `max_tokens` cap
- Anthropic messages (non-stream) with enforced `max_tokens` cap
- usage ledger logging
- optional evidence emission to Cynsta ingest via `CynstaTracer`

### 5.2 Storage Backends

`CAP_STORE=sqlite` (sidecar default):

- local sqlite DB `cynsta-spendguard.db`
- one in-flight run per agent enforced via a lock field (simple, deterministic)

`CAP_STORE=supabase` (hosted default):

- Supabase tables created by `infra/supabase/migrations/20260208180000_create_cap_tables.sql`
- API auth uses existing `api_keys` and requires `cap:use` scope

### 5.3 API Surface (MVP)

- `POST /v1/agents` -> `{ agent_id }`
- `GET /v1/agents` -> `{ agents: [{ agent_id, name, created_at }, ...] }`
- `POST /v1/agents/{agent_id}/budget` body `{ hard_limit_cents, topup_cents }`
- `GET /v1/agents/{agent_id}/budget`
- `POST /v1/agents/{agent_id}/runs` -> `{ run_id }`
- `POST /v1/agents/{agent_id}/runs/{run_id}/openai/chat/completions`
- `POST /v1/agents/{agent_id}/runs/{run_id}/openai/responses`
- `POST /v1/responses` (OpenAI SDK compatibility; requires `x-cynsta-agent-id`)
- `POST /v1/agents/{agent_id}/runs/{run_id}/gemini/generateContent`
- `POST /v1/agents/{agent_id}/runs/{run_id}/anthropic/messages`

OpenAI minimal compatibility endpoint:

- `POST /v1/chat/completions`
- requires header `x-cynsta-agent-id: <uuid>`
- optional `x-cynsta-run-id: <uuid>`

### 5.4 Evidence Emission

If `CAP_INGEST_URL` and `CAP_INGEST_API_KEY` are set, the gateway emits:

- an LLM span containing prompt/response (configurable capture)
- a tool envelope `cynsta.cap.settlement` containing accounting metadata

This reuses the existing `packages/cynsta-langchain` OTEL exporter patterns.

### 5.5 Billing Breakdown (v2)

SpendGuard stores a normalized `billing_breakdown` in the usage ledger `meta_json` for reconciliation and audit:

- charges are priced in integer `microcents` (1e-6 of a cent)
- budgets settle using `realized_cents_ceiled` (single ceiling after summing line items)

Rate tables are overrideable via `CAP_PRICE_TABLE_JSON`; see `apps/cynsta-spendguard/README.md`.

## 6. Known Limitations (Intentional MVP Cuts)

- No streaming mid-generation cancellation yet.
  - Hard cap is enforced by clamping `max_tokens` and rejecting unaffordable requests.
- Pricing uses conservative defaults and requires ops hygiene:
  - override with `CAP_PRICE_TABLE_JSON` and keep it updated.
- Credits checkout flow is not implemented yet.
  - Hosted mode can “top-up” budgets via API, but payments are out-of-scope for MVP.
- Multimodal inputs are rejected (fail loudly) because modality-aware tokenization/pricing is not implemented.

## 7. How To Run / Test (MVP)

Run locally (sidecar sqlite):

See `apps/cynsta-spendguard/README.md`.

CLI budget set command:

```powershell
pip install cynsta-spendguard
spendguard agent create --name "agent-1"
spendguard agent list
spendguard budget set --agent <agent_id> --limit 5000 --topup 5000
spendguard budget get --agent <agent_id>
```

Unit tests:

```powershell
$env:PYTHONPATH="apps/cynsta-spendguard"
python -m unittest discover -s apps/cynsta-spendguard/tests -p "test_*.py"
```

## 8. Next Work (Concrete, High ROI)

1. Add streaming support + cancellation for OpenAI streaming responses.
2. Implement Anthropic:
   - 200k tier selection preflight
   - cache write/read usage parsing
3. Replace token estimation with real tokenizers (only if needed; keep dependencies permissive).
4. Implement hosted credits ledger:
   - account-level credit balance
   - per-agent budgets draw down from credits
5. Make training/capture policy explicit and enforceable:
   - hosted default yes (per account flag)
   - sidecar default opt-in

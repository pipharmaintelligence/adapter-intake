# Pharma 0.1.9 — Planner contract hardening and live-readiness closure

Asset candidate: `nusaibah.pharma_company_intelligence_lab@0.1.9`.
This development checklist is not part of promoted runtime bytes.

## Package scope

- [x] New immutable asset version `0.1.9`; retain all older published versions.
- [x] Explicit `provider_policy.timeout_seconds`: planner/benchmark 60, research 120, analysis/critic/synthesis 180.
- [x] New planner contract/chain `1.0.4`; all other roles remain `1.0.2`.
- [x] Runtime floor `pi-obs-python-runtime>=0.1.92`.
- [x] Version-owned adapter adds thread-safe logical call budgets: 12 per company in preview, 13 in apply, at most 5 companies and 4 planner iterations.
- [x] Guard counts failed dispatches, rejects unknown role/company scope and checks whole-batch committed-benchmark capacity before mutations.
- [x] Shared helpers, prompts, model/token/thinking/search policy, provider references, call counts and storage contracts unchanged.
- [x] Task deadline remains 1800 seconds; caller inputs contain no provider timeout overrides.
- [x] Planner response contract explicitly mirrors validator field types, required values, item minima/maxima, non-empty text, text bounds, normalization and duplicate rules.
- [x] Planner/iteration failures attach enum-only diagnostic metadata; no model content is embedded.
- [x] README defines Core policy/environment, worker/queue budgets, admission order, safe proof and rollback.

## Local proof

- [x] Pharma suite: 130 tests, including local-root and packaged dotted imports, repeating planner iterator, concurrent duplicate calls and pre-mutation budget exhaustion.
- [x] Repository promotion-shape test passes.
- [x] Focused intake check passes.
- [x] Repository-wide intake check: 18 ready, zero blocked.
- [x] CI runs pharma manifest/authority, import identity, iteration-limit, and orchestration planner contract-parity checks.
- [ ] Fresh 0.1.9 focused suite is green on the PR head.
- [ ] Exact final intake SHA is merged and pinned for Assets promotion.
- [ ] Promotion verifies retained versions and version-owned dependency metadata.

## Deployment and live proof

These remain operational acceptance gates, not claims made by offline tests.

- [ ] Core #158, Assets #444/#453 (or descendants), and runtime 0.1.92+ are deployed.
- [ ] Exact Core registration policy permits 180-second requests while preserving unrelated fields.
- [ ] Core material TTL is 240 seconds and scoped session ceiling is 1800 seconds.
- [ ] Worker uses admission v2; task authority is bounded and never extended by refresh.
- [ ] Separate cleanup budget 60 seconds, job timeout 1920 seconds, queue reservation greater than job timeout and supervisor grace verified.
- [ ] Exact 0.1.9 Companies binding and worker catalog are ready.
- [ ] All eight new Agent versions pass dry-run before application; older chains are retained.
- [ ] New session shows requested 60/120/180-second budgets with sufficient material lifetime.
- [ ] Company 13 preview completes the entire graph without mutation/publication.
- [ ] Existing Bedrock primitive remains valid under the deployment profile.
- [ ] Memory apply and dossier publication are certified separately when requested.

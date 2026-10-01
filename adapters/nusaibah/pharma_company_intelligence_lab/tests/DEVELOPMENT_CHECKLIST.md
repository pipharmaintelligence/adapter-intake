# Pharma 0.1.8 — Governed provider budgets

Asset candidate: `nusaibah.pharma_company_intelligence_lab@0.1.8`.
This development checklist is not part of promoted runtime bytes.

## Package scope

- [x] New immutable asset version `0.1.8`; retain all older published versions.
- [x] Explicit `provider_policy.timeout_seconds`: planner/benchmark 60, research 120, analysis/critic/synthesis 180.
- [x] New planner contract/chain `1.0.3`; all other roles `1.0.2`.
- [x] Runtime floor `pi-obs-python-runtime>=0.1.91`.
- [x] Adapter implementation changes only its version identity.
- [x] Shared helpers, prompts, model/token/thinking/search policy, provider references, call counts and storage contracts unchanged.
- [x] Task deadline remains 1800 seconds; caller inputs contain no provider timeout overrides.
- [x] README defines Core policy/environment, worker/queue budgets, admission order, safe proof and rollback.

## Local proof

- [x] Pharma suite: 119 tests, including local-root and packaged dotted imports.
- [x] Repository promotion-shape test passes.
- [x] Focused intake check passes.
- [x] Repository-wide intake check: 18 ready, zero blocked.
- [x] CI runs the pharma manifest/authority and import-identity checks.
- [ ] Exact final intake SHA is merged and pinned for Assets promotion.
- [ ] Promotion verifies retained versions and version-owned dependency metadata.

## Deployment and live proof

These remain operational acceptance gates, not claims made by offline tests.

- [ ] Core #158, Assets #444 (or descendants), and runtime 0.1.91 are deployed.
- [ ] Exact Core registration policy permits 180-second requests while preserving unrelated fields.
- [ ] Core material TTL is 240 seconds and scoped session ceiling is 1800 seconds.
- [ ] Worker uses admission v2; task authority is bounded and never extended by refresh.
- [ ] Separate cleanup budget 60 seconds, job timeout 1920 seconds, queue reservation greater than job timeout and supervisor grace verified.
- [ ] Exact 0.1.8 Companies binding and worker catalog are ready.
- [ ] All eight new Agent versions pass dry-run before application; older chains are retained.
- [ ] New session shows requested 60/120/180-second budgets with sufficient material lifetime.
- [ ] Company 13 preview completes the entire graph without mutation/publication.
- [ ] Existing Bedrock primitive remains valid under the deployment profile.
- [ ] Memory apply and dossier publication are certified separately when requested.

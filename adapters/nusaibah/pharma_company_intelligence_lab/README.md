# Nusaibah Pharma Company Intelligence Lab

Canonical adapter-intake source for `nusaibah.pharma_company_intelligence_lab`.

## Current release

- `0.1.0` is an immutable published Assets identity.
- `0.1.1` is the corrective adapter-intake release for remote Agent admission compatibility.
- The correction does not change business orchestration, prompts, Fixed Skill bytes, Dynamic Skill behavior, model selection, thinking levels, search policy, provider binding selectors, or canonical dossier structure.
- The correction makes every packaged Agent reuse one canonical shared `provider:text_generation@1.0.0` registry entry.

Do not rewrite or republish `0.1.0` in place. Any package-byte correction after publication must use a new asset version.

## Shared Agent registry contract

All eight Agent definitions depend on the same runtime registry identity:

```text
handle = provider:text_generation
version = 1.0.0
owner_client_id = null
```

That registry entry is shared infrastructure, not Agent-specific configuration. Its full definition must remain byte-equivalent across all eight roles and compatible with the established Assets provider registry. For `0.1.1`, the canonical registry metadata is:

```text
provisioning_source = pi_1895_capability_lab
```

Agent- or asset-specific provenance belongs on each Agent chain's `metadata`, where the chain identities are distinct. Do not place role-specific provenance in the shared registry entry: current Assets admission treats registry metadata as identity-significant and rejects conflicting definitions.

## Eight-Agent architecture

The packaged roles are:

1. `methodology_planner`
2. `portfolio_researcher`
3. `market_researcher`
4. `regulatory_risk_researcher`
5. `strategic_analyst`
6. `evidence_critic`
7. `intelligence_synthesizer`
8. `memory_benchmark_reviewer`

Only the three research roles have provider-grounded public search authority. The planner, strategic analyst, critic, synthesizer, and benchmark reviewer cannot introduce new public facts.

## Batch and benchmark contract

The target launch variable is a bounded `company_ids` array such as `[13, 59]`. Assets/Core resolves the governed `companies` input before Python starts. The adapter validates exact requested/resolved ID parity and processes each company context independently.

A multi-company batch proves isolation and composition only. There is no cross-company benchmark, ranking, scoring, winner selection, or comparative assessment. `memory_benchmark_reviewer` evaluates one company's own memory before/proposed/committed states only.

## Format ownership

`dossier_contract.py` owns exact section IDs, subsection IDs, titles, and order. Agents return machine IDs and content only. Titles and hierarchy are rendered deterministically by the adapter so report structure cannot drift by provider, company, or run.

## Runtime compatibility

The adapter declares `pi-obs-python-runtime>=0.1.84`. The `0.1.1` correction must be certified against the selected local wheel and current Assets package boundary before promotion.

The adapter owns no provider credentials, direct provider SDK calls, storage placement, OBS/Core transport, asynchronous workers, retries, queues, or publication authority.

## Promotion and admission sequence

This folder is the reviewed source package. Use only the pinned adapter-intake promotion pathway:

```text
local/intake validation
-> exact immutable intake SHA
-> pinned Assets P8 validation
-> adapter-intake-promote-pr.yml
-> generated Assets PR
-> Assets CI
-> merge/deploy
-> eight-role obs-agent-runtime-admit dry-run
-> eight-role admission apply
-> primitive live proofs
-> combined live composition
```

Do not hand-edit the packaged Assets directory, recreate the generated promotion PR manually, or use `--update-existing` merely to suppress an admission conflict.

Development progress and release evidence are tracked in Linear PI-1951 / PI-1954 and in the development-only `tests/DEVELOPMENT_CHECKLIST.md`; that checklist is intentionally excluded from promoted runtime bytes.

# Nusaibah Pharma Company Intelligence Lab — 0.1.1

This document describes the corrective `0.1.1` release of
`nusaibah.pharma_company_intelligence_lab`.

The existing `README.md` is deliberately preserved byte-for-byte because it
is already part of the immutable published `0.1.0` package. Current Assets
materialization requires shared support files to remain identical when a prior
version is preserved.

## Why 0.1.1 exists

`0.1.0` passed local/intake validation, pinned Assets package validation, and
the documented promotion workflow. After deployment, remote Agent admission
returned:

```text
agent_runtime_provisioning_conflict
```

Current Assets admission uses the tuple
`handle + version + owner_client_id` as the Agent registry identity and
compares the full reviewed registry definition, including metadata.

All eight pharma Agents use the shared provider registry identity:

```text
handle = provider:text_generation
version = 1.0.0
owner_client_id = null
```

The `0.1.0` manifest attached role/asset-specific provenance metadata to this
shared registry entry. That made otherwise identical shared-provider registry
definitions conflict.

## 0.1.1 correction

All eight Agent definitions now reuse the same canonical shared registry entry.
Its metadata matches the already-established Assets registry contract:

```text
provisioning_source = pi_1895_capability_lab
```

Agent-specific provenance remains on each distinct Agent chain's `metadata`.

The adapter class identity, intake contract, and manifest default are all
`0.1.1`.

## Behavior intentionally unchanged

The correction does not change:

- the eight Agent roles;
- business orchestration;
- Fixed Skill bytes or digest;
- Dynamic Skill read/mutation behavior;
- canonical dossier sections or titles;
- model selection;
- thinking levels;
- provider-grounded search authority;
- citation policy;
- ProviderVault selectors;
- Agent prompts;
- deterministic quality gates;
- expected-digest mutation safety;
- publication ownership.

## Benchmark scope

There is no cross-company benchmark, ranking, scoring, winner selection, or
comparative assessment between company IDs.

A batch such as `[13, 59]` proves isolation and composition only. The
`memory_benchmark_reviewer` evaluates each company's own memory lifecycle.

## Runtime compatibility

Minimum runtime remains:

```text
pi-obs-python-runtime >= 0.1.84
```

The correction is being certified against runtime `0.1.88` and current Assets
materialization/admission contracts.

## Promotion and admission sequence

```text
adapter-intake deterministic validation
-> official intake checks
-> immutable 0.1.1 SHA
-> pinned Assets P8
-> adapter-intake-promote-pr.yml
-> generated Assets PR
-> Assets CI
-> merge/deploy
-> eight Agent dry-run admissions
-> eight Agent apply admissions
-> primitive live proofs
-> combined live composition
```

Do not hand-edit the Assets package and do not use `--update-existing` merely
to suppress an admission conflict.

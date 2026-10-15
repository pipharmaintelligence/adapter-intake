# Objective

Run one targeted company enrichment pass and publish validated memory and methodology through the existing Core Dynamic Skill ZIP/partition lane. Critic, evidence and benchmark work is automated enrichment validation, not human approval.

# System Context

Company Scope owns the approved Companies query and supplies retained CompanyContext. Pharma never queries Companies again. The standalone E runner controls the bounded company-ID loop; it is not adapter code and owns no database or storage authority.

```mermaid
flowchart LR
    C[Company Scope] --> P[CompanyContext]
    P --> S[Section planner chunks and optional learned methodology]
    S --> R[One targeted specialist pass over literal source chunks]
    R --> E[Exact evidence spans and semantic checks]
    E --> B[Critic, synthesis and per-question benchmark]
    B --> D[Append source-verified section deltas; preserve existing memory]
    D --> K[Existing Core Dynamic Skill ZIP upload, CAS and history]
    K --> V[Fresh storage-backed readback]
    V --> L[E runner: last-success checkpoint only]
```

# Approach

Use `memory_mode=apply`, `portfolio_review_passes=1`, and `publish_dossier=false`. Readonly preparation is an internal phase of the same execution; it is not another preview workflow or a manual approval step. `preflight_only=true` remains a separately requested readonly diagnostic and requires preview intent. No `review_decision` or `reviewed_result` input is required for production enrichment.

Existing section planner calls, canonical section/subsection IDs and specialist boundaries remain. The portfolio specialist covers its two assigned sections as a bounded batch; this does not claim a distinct model call for every subsection. Source excerpts are literal 900-character chunks, at most twelve per specialist invocation, with stable chunk IDs and original offsets. The full trusted source snapshot remains the exact-span validation authority. Selected excerpts are not a complete-document dump and absence is not evidence of a global negative.

Research chains return v3 JSON in one provider turn using already retrieved sources. A separate native-search notes-to-formatter chain is not used in this new version: that chain repeated the original context plus intermediate notes and exceeded the current 64,000-character policy on the 0.1.26 live case. Provider JSON validation and the existing one-time faithful response resolver remain. Native search in historical versions is unchanged.

# Changes Made

The new version packs source chunks and avoids forwarding existing memory twice to research. All enrichment Agent inputs have a 42,000-character business-input bound, leaving framing/prompt headroom under the currently observed Core policy. Core still owns the authoritative limits. Four bounded section critics replace the aggregate critic. There are at most 15 ordinary Agent invocations per company, or 30 including one faithful backup for each; no unbounded retry or reflection loop. Each request retains 600 seconds and 32,000 output tokens. The whole execution remains finite at 1,800 seconds.

Automated checks validate selected claim evidence, company/section scope, each selected section's critic result and per-question benchmark non-regression. They do not pretend to provide human attestation. Supported deltas can proceed when another research claim is withheld; rejected claims never enter stored facts. An unresolved section keeps its negative verdict and withheld facts in the annex. The overall critic is never rewritten to pass; only validated sibling sections may publish. A partial critique does not produce a supposedly passed planner-learning snapshot. Existing deterministic procedural lessons remain separate from factual research. New factual section deltas are appended without replacing the existing curated section or deleting its other evidence. Unsupported, unavailable and inapplicable work remains explicit in the result/annex.

# Modularity Impact

No raw HTTP, SQL, provider client, storage credentials, new governance lane or AssetPublishPolicy is added to the adapter. Existing RuntimeInputs readers and the pinned exact-span toolkit supply evidence. Existing Core Skill changesets supply ZIP preparation/upload, compare-and-swap, archive preservation, history and readback. The E runner receives small publication outcomes and records only checkpoints, not dossiers, source documents or ZIP files on disk.

All historical Python helpers and manifest contracts remain immutable. This is a new opt-in asset version; it does not change existing running assets or require a runtime version bump. Use official workflow promotion and its official artifact for delivery.

# Validation

Required checks cover stable literal source offsets, section/subsection packing, input caps before dispatch, preservation of existing memory, selected-fact evidence, per-question benchmark regression, automatic apply without reviewer input, stale package detection, no-change behavior and truthful partial commits. Deterministic fixtures are not live storage proof. A live cycle must verify actual uploads, selected partition state, fresh content/package digests and history before it is described as published.

# Risks / Open Questions

- Apply currently needs initialized selected packages. An absent package is reported explicitly; a missing memory or methodology package does not invent an empty seed or bypass Core creation authority. First-package initialization remains an existing ordinary authorized DLM ZIP/partition operation and must be completed before a company can fully close publication.
- Memory and methodology commits are independent. A partial/unconfirmed commit keeps its available receipt and is not blindly retried; the runner must not advance its last-success checkpoint.
- No-change content produces no fake ZIP upload/history entry. A successful unchanged result is distinguished from an actual upload.
- Public excerpts can be thin or unavailable. Stored memory remains historical evidence, not fresh independent public evidence or authority to alter Companies.
- This version is not live-qualified until its real publication cycle passes. One local-worker case does not prove broad factual calibration, all companies, or ECS execution.

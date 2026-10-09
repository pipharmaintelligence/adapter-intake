# Company Scope â€” bounded 0.1.0 and native-page 0.1.1

PI-2011: additive, deterministic CompanyContext assembly from the existing
binding-only Companies input. The working pharma/evaluation 0.2.3 path and its
retained evidence are unchanged.

## Release boundary

This is a **development candidate**, not a governed live-proof receipt.
Keep the intake PR draft and do not promote, register, enable, or live-launch
until the server readiness gates in DEVELOPER_GUIDE.md have evidence.

The runtime requires an active default in a valid manifest. Consequently
`versions.*.state = active` is a supported manifest declaration, not proof
that a server binding, query policy, or downstream handoff has been installed.
`release_stage: development` is intake metadata; it is not a runtime security
switch. The required `companies` role is binding-only, never caller-provided
live data.

Python validates the rows it receives. It cannot enforce which rows/columns
Core fetched before hydration, authenticate a copied provenance object, or
retroactively prepare a selector for an already-executed query. Every output
therefore keeps `runtime_authority_verified = false`. Bounded outputs use
`validation_scope = resolved_rows_only`; native-page outputs use
`validation_scope = resolved_page_only`.

## Responsibilities

```text
Caller selector
  -> Assets: validate/normalize before retrieval [server gate]
  -> Core: authorized Companies query, source `corporate=1`, approved columns [server gate]
  -> Company Scope: exact-set checks and CompanyContext[] [this asset]
  -> OBS: future bounded handoff [separate proof]
  -> compatible analysis consumer -> existing governed memory flow

Preserved reference: existing 0.2.3 -> existing toolkit -> retained evaluation.
```

Scope has no SQL, HTTP, database connections, storage access, Agent calls,
Dynamic Skill calls, callable children, retries, or downstream orchestration.
The Companies operation remains Core-owned. Memory/history remains owned by
Core/Dynamic Skill. The memory boundary denotes write authority, not failure.

## Bounded selection â€” version 0.1.0

Use asset version `0.1.0` and supply exactly one form in `variables`:

```json
{"company_id": 1001}
```

```json
{"company_ids": [1002, 1001, 1002]}
```

```json
{"from_company_id": 1001, "to_company_id": 1003}
```

Rules:

- Positive integers only, excluding booleans and numeric strings.
- IDs must fit the contract's signed 64-bit positive identifier ceiling.
- Maximum raw list length 25; maximum inclusive range width 25.
- Deduplicate input IDs preserving first occurrence; report duplicate count.
- Ascending inclusive ranges; reject reversed ranges before expansion.
- Reject extra options, fields, corporate overrides, and mixed selector forms.
- All requested IDs must resolve after corporate scoping. No partial mode.
- Missing selectors and empty lists fail; neither means all companies.

`normalize_selector()` is a pure specification for server preparation and
adapter defense. Using it during adapter execution does not supply the missing
pre-query server stage. Current `id <- company_ids` list membership is supported;
single/range live preparation is not established by this candidate.

## Resolved bounded Companies contract â€” version 0.1.0

`companies` must match the current Assets `safeDlmNodePythonInputPayload`:
`records`, `row_count`, `exactness`, `partial_reason`, and `provenance`.
Require exactness `exact`, no partial reason, at most 25 rows, matching count,
source/authority `dlm_node`, node key `companies`, a safe logical lake ID,
and a positive integer `pages_read` (excluding booleans). Optional input mode
may be `bounded_query`. Complete results aggregated by Assets across multiple
pages are accepted; pagination limits and cursor handling remain server-owned.
Bare lists, lazy descriptors, full dumps, partial results, and unknown fields fail.

Approved row fields (the source has both `corporate` and `corporate_id`; only
`corporate` expresses membership and is projected):

| Source | CompanyContext |
| --- | --- |
| `id` | `company_id` (required) |
| `company` | `company_name` (required, nonblank) |
| `corporate` | `corporate_id` (required integer 1) |
| `address_line1`, `address_line2` | Same names, optional |
| `headquarter` | `headquarters_country_id`, optional positive country FK |
| `website` | `website`, optional |
| `updated_at` | `source_updated_at`, optional source text |

Reject every other row column, including `remember_token` and account/admin
fields. Strings are bounded and never silently truncated. Missing optional
fields become null. Country names, city, registration number, and status are
not fabricated. Corporate membership is a business invariant, separate from
client/lake authorization.

## Page size, batch size, and larger selections

These are separate controls:

- **Page size:** Assets/Core determine how many rows each query request returns.
  The reviewed binding descriptor uses 25 as its page size. Existing Assets
  pagination can aggregate further pages under the authorized server policy.
- **Adapter batch size:** at most 25 raw requested IDs, 25 IDs in an inclusive
  range, and 25 returned rows per Scope invocation. Multiple source pages do
  not increase this ceiling or initiate another query from Python.
- **Total workflow scope:** larger selections need explicit server coordination,
  a total company cap, checkpoints, and per-company execution budgets. This
  candidate does not implement whole-selection coordination. Version 0.1.1
  below accepts explicit all_authorized intent and one already-prepared page;
  it does not enable server dump admission.

Use existing Assets/Core pagination; do not duplicate cursor or retry loops in
this adapter. Hitting a page, row, or time cap yields an incomplete source and
must fail Scope even when some requested records are already present.
See DEVELOPER_GUIDE.md for the existing paths and future batch handoff rules.

## Native full-dump pages â€” development version 0.1.1

Version 0.1.1 requires an explicit semantic selection:

```json
{"selection": "all_authorized"}
```

The required Companies role remains binding-only. Caller selection does not
switch server query mode, authorize a dump, or supply company records. The
current governed binding service rejects full-dump enablement and fixes its
query mode to bounded_query; this candidate is not live-admitted there.

The new adapter consumes the existing safe full_dump_async page envelope:
records, row_count, exactness, partial_reason, and provenance containing logical
source/authority/lake/node, pages_read=1, input_mode=full_dump_async, page_index,
and record_offset. No cursor, next URL, credential, or checkpoint is passed to
Python. Every page is capped at 25 approved company rows with source `corporate=1`.

Normal continuation (partial / more_pages_available) is accepted without
relabeling the source exact. Policy/time caps, unknown/inconsistent states,
malformed positions, and an empty nonterminal page fail. An empty exact terminal
page is valid. Server ordering is preserved and the same row checks/DTOs used by
0.1.0 apply. Cross-page membership, progress, and retries remain server-owned.

Output `company_scope_page` uses company_scope_page.v1:

- batch_complete=true: all rows in this delivered page were validated;
- source_exhausted=false for continuation, true for an exact terminal page;
- selection_complete=null: the adapter cannot attest earlier-page processing;
- completion_scope=current_page, original source exactness/partial reason,
  page position, bounded contexts, and a deterministic content/position digest.

The scalar company_scope_summary contains no company names, IDs, or digests.
Resume is declared for 0.1.1 so the framework can invoke another prepared page;
the adapter has no resume loop, checkpoint persistence, or accumulated history.
Declare/enable no live binding until the developer-guide admission, asynchronous
queue, per-page retention/readback, scope/projection, and total-budget gates pass.
An active default or allow_resume declaration does not satisfy those gates.

## Outputs â€” bounded version 0.1.0

- `company_scope_result`: versioned envelope containing caller-ordered
  `contexts`, requested IDs, counts, complete status, and content digest.
- `company_scope_summary`: scalar counts/limits/status only, suitable for the
  existing summary projection. No company IDs, names, or content digests.

Each `company_context.v1` carries safe logical source identity and its own
content digest. Current hydration does not expose retrieval time or source
schema version; those fields remain null. Adapter code does not substitute its
clock, DTO version, or a hardcoded Companies schema revision for source metadata.
A content digest is integrity metadata, not an authorization signature.

Errors are fixed `company_scope_*` codes with no company values. A failure in
any row aborts the entire invocation before returning outputs. Every company
and every invocation receives fresh mutable output dictionaries.

## Offline verification in DataSpell / PowerShell

```powershell
$IntakeRoot = 'E:\nusaibah_projects\demo_asset_project\adapter-intake-work'
$Python = 'E:\nusaibah_projects\demo_asset_project\.venv\Scripts\python.exe'
Set-Location -LiteralPath $IntakeRoot
& $Python -m unittest discover -s tests -p 'test_company_scope*.py' -v
& 'E:\nusaibah_projects\demo_asset_project\.venv\Scripts\obs-adapter-intake-check.exe' `
    --adapter-yaml "$IntakeRoot\adapters\nusaibah\company_scope\adapter.yaml" --pretty
```

The synthetic resolved fixture under `tests/fixtures` is for offline tests and
local package diagnostics only. It is not a caller launch file, binding receipt,
or evidence about real Companies records. Tests/fixtures are excluded from
promotion. No .env file or provider run is needed for these checks.

## Promotion and integration

Use the official adapter-intake promotion workflow after server gates are
proven. Do not hand-copy this candidate into Assets, edit packaged source,
upgrade the E runtime, or replace existing production bindings.

Both versions admit `local_worker` only and do not declare a
callable contract. A parent around the existing 0.2.3/toolkit chain conflicts
with the reviewed nesting restriction. Workflow handoff and a future
CompanyContext-aware consumer need separate manifest, authority, and regression
proof. No memory preview/apply or provider launch is part of this candidate.

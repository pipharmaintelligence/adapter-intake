# Company Scope 0.1.0

PI-2011: additive, deterministic CompanyContext assembly from the existing
binding-only Companies input. The working pharma/evaluation 0.2.3 path and its
retained evidence are unchanged.

## Release boundary

This is a **development candidate**, not a governed live-proof receipt.
Keep the intake PR draft and do not promote, register, enable, or live-launch
until the server readiness gates in DEVELOPER_GUIDE.md have evidence.

The runtime requires an active default in a valid manifest. Consequently
`versions.0.1.0.state = active` is a supported manifest declaration, not proof
that a server binding, query policy, or downstream handoff has been installed.
`release_stage: development` is intake metadata; it is not a runtime security
switch. The required `companies` role is binding-only, never caller-provided
live data.

Python validates the rows it receives. It cannot enforce which rows/columns
Core fetched before hydration, authenticate a copied provenance object, or
retroactively prepare a selector for an already-executed query. Every output
therefore says `validation_scope = resolved_rows_only` and
`runtime_authority_verified = false`.

## Responsibilities

```text
Caller selector
  -> Assets: validate/normalize before retrieval [server gate]
  -> Core: authorized Companies query, corporate_id=1, approved columns [server gate]
  -> Company Scope: exact-set checks and CompanyContext[] [this asset]
  -> OBS: future bounded handoff [separate proof]
  -> compatible analysis consumer -> existing governed memory flow

Preserved reference: existing 0.2.3 -> existing toolkit -> retained evaluation.
```

Scope has no SQL, HTTP, database connections, storage access, Agent calls,
Dynamic Skill calls, callable children, retries, or downstream orchestration.
The Companies operation remains Core-owned. Memory/history remains owned by
Core/Dynamic Skill. The memory boundary denotes write authority, not failure.

## Selectors

Supply exactly one form in `variables`:

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

## Resolved Companies contract

`companies` must match the current Assets `safeDlmNodePythonInputPayload`:
`records`, `row_count`, `exactness`, `partial_reason`, and `provenance`.
Require exactness `exact`, no partial reason, at most 25 rows, matching count,
source/authority `dlm_node`, node key `companies`, a safe logical lake ID,
and a positive integer `pages_read` (excluding booleans). Optional input mode
may be `bounded_query`. Complete results aggregated by Assets across multiple
pages are accepted; pagination limits and cursor handling remain server-owned.
Bare lists, lazy descriptors, full dumps, partial results, and unknown fields fail.

Approved row fields:

| Source | CompanyContext |
| --- | --- |
| `id` | `company_id` (required) |
| `company` | `company_name` (required, nonblank) |
| `corporate_id` | `corporate_id` (required integer 1) |
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
  candidate does not implement that coordinator or an all-companies selector.

Use existing Assets/Core pagination; do not duplicate cursor or retry loops in
this adapter. Hitting a page, row, or time cap yields an incomplete source and
must fail Scope even when some requested records are already present.
See DEVELOPER_GUIDE.md for the existing paths and future batch handoff rules.

## Outputs

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
& $Python -m unittest discover -s tests -p 'test_company_scope.py' -v
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

The manifest currently admits `local_worker` only and does not declare a
callable contract. A parent around the existing 0.2.3/toolkit chain conflicts
with the reviewed nesting restriction. Workflow handoff and a future
CompanyContext-aware consumer need separate manifest, authority, and regression
proof. No memory preview/apply or provider launch is part of this candidate.

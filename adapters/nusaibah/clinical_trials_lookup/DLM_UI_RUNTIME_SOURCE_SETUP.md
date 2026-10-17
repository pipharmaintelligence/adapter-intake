# DLM UI authoring and qualification — ClinicalTrials.gov lookup 0.1.0

Status: **SOURCE-REVIEWED GUIDE + USER-SUPPLIED CORE DRAFT READINESS; NO PROVIDER FETCH PROVEN**.
Scope: `nusaibah.clinical_trials_lookup@0.1.0`, PR #147 only; no platform code, credential, asset publishing, or clinical-failure change.
Reviewed on 2026-10-17 against DLM UI `3cd45971e0484327c7a33f91758d82a97d5ad59b`, Core `f6145a9af38b142710f4a6e892e7fc772b1e4aad`, Assets `12904cbe39da79034ba873b86e0466f1a8a27b3a`. This is source evidence, **not a deployed version assertion**.

## 1. Screen and first native source

Open the application's existing `/platform/providers?tab=mcp-tools&mcp_tab=runtime-sources` section. Check the inventory for an existing native `@clinical_trials_gov_v2` in the authorized client/lake scope first. Do not overwrite/recreate an existing handle or rely on Linear PI-1752 as current database state. If absent, select **Create Runtime Source** (not Create MCP connector).

Use the public ClinicalTrials.gov API v2 studies GET endpoint in the write-only Request URL field. The request target exists only in Core runtime configuration, not Python, adapter manifests, fixtures or response projections.

| Visible field | Initial intended value | Qualification |
| --- | --- | --- |
| Client ID | exact authorized client from the signed-in tenant/environment | **Unknown** until UI/Core readback |
| Lake ID | blank (client-wide) unless actual policy requires lake scoping | Core client-wide regression gives `node_binding=not_required` |
| Runtime handle | `@clinical_trials_gov_v2` only if unique | historical PI-1752 proposal, **not existing-source proof** |
| Provider / server ref | `clinicaltrials_gov` | UI maps this to Core `provider_family`, not a credential |
| Capability ref | `clinical_trials.studies.query` | same logical capability as PI-1752; maintain exact value on subsequent calls |
| Operation | `query_studies` | source operation identifier; separate from business `study_search` |
| Context label | `ClinicalTrials.gov API v2 studies` | descriptive only |
| Auth scheme | `public` | official public GET; no credential profile, no secret |
| Method / Response format | `GET` / `json` | source API returns JSON |
| Query parameter name | `query.term` | used for runtime `input.text` if invoked; adapter currently passes named parameters |
| Max records | `1` | one **root page object**; this is not number of studies |
| Pagination mode | `none` | the native source UI exposes none/page, **not cursor**; adapter owns one-page `pageToken` requests |
| Records path | blank | v2 GET r2 must preserve root `studies`, optional `nextPageToken`/`totalCount` |
| Automated client identity | `none` initially | change to required + approved nonsecret identity only if local policy needs it |
| Execution substrate | `local_worker` ON; `ecs` OFF | current PR manifest is local-worker-only |

Allowed input parameters (comma-separated in the current UI), derived **exactly from the current adapter search/batch code**, not a declaration that each value already executes on a live worker:

```text
query.term,query.cond,query.intr,query.titles,query.outc,query.spons,query.lead,query.locn,query.id,query.patient,filter.ids,filter.overallStatus,filter.advanced,pageSize,countTotal,pageToken,sort
```

The UI allows at most 25 safe parameter names; these 17 names satisfy the UI/Core name pattern. The basic `study_search` validation sends `query.intr`, `pageSize=10`, `countTotal=true`. No broad no-selector scan. The current trusted lazy-variable validator rejects some provider Essie expressions and opaque cursor strings; **never** bypass it or add direct provider HTTP to Python.

**Do not write the request URL into adapter code or fixture metadata.** For public `GET`, the UI does not display its Request format selector; the underlying draft form uses `json`. Leave pagination mode `none` rather than inaccurately configuring ClinicalTrials.gov cursor pagination as page-number pagination.

## 2. Save/observe without inventing live results

1. Save **Runtime Source draft** and note the safe `rt_src_...` reference / exact client and handle from Core.
2. On the Runtime Sources list, select **Recheck readiness** and inspect `checks` and `node_binding`. While draft, `source_published` is correctly blocked: Core's readiness gate requires `active`.
3. If client-wide, Core test proves `node_binding.status=not_required`; do **not** press Bind node. If lake-scoped, follow Core's actual `can_bind` and `next_action` rather than assuming a node.
4. When source identity/authority/required node setup are correct, use the existing **Publish** action. Recheck readiness; require Core `readiness_status=ready`, no blocked checks, correct source ref/client/substrate.
5. The current MCP & Tool Runtimes workspace deliberately has **no Run/Execute/Invoke control**. A `ready` projection only proves configured source admission checks, **not an HTTP round trip**.
6. An operator then performs one authorized, signed `local_worker` run using exact admitted `trials_search_runtime` input role, selected Core source ID, source operation/capability, one simple intervention value, `pageSize=10` and no continuation token. Verify the runtime returned **one** root object under `records[0]` containing `studies` (a list). Inspect optional `nextPageToken`/`totalCount`, selected IDs, safe record count, and adapter terminal status. A semantic business result is not raw provider proof and a zero-row result is not always a connection failure.
7. After the basic operation succeeds, separately prove multi-filter expressions, alias quoting, continuation, study detail and arm/outcome/results projections before marking additional operations as runtime-qualified.

## 3. The other two technical input roles are separate sources

PR #147 has **three source roles**, not one arbitrary generic endpoint:

- `trials_search_runtime`: the first source described above; source handle and `rt_src_...` are not the same thing as a manifest role name.
- `trials_detail_runtime`: separately governed exact-study GET target with Core-owned path template and a single allowlisted `nct_id`; JSON **study object** becomes one record with empty records path. This is needed for `study_get`, `arms_get`, `outcomes_get`, `results_get`.
- `trials_phase3_runtime`: separately governed Phase 3/interventional study search. The current Core implementation **can** preserve configured query-string values from a reviewed source target in short-lived trusted execution material and rejects caller collisions. Configure/review a fixed advanced filter there only after the baseline source is proven; do not assume a distinct handle automatically guarantees Phase 3 scope. Verify the actual returned phase and study type.

A saved Core source does **not** automatically attach a lazy runtime role to the draft PR. Exact role-to-source admission and safe variable resolution occur in the Assets/worker execution path. The initial manifest declares these as optional direct technical roles; preserve trust boundaries.

## 4. Verification ledger to complete with observed evidence

| Proof gate | Recorded state as of this document | Safe evidence to add later |
| --- | --- | --- |
| Current UI page/source form contract | source-reviewed | UI SHA, source file paths |
| Core client-wide source/no-node contract | source+feature-test covered | Core SHA, `node_binding.status` |
| Core root-object JSON r2 executor | source/test covered default; deployment unknown | Actual executor revision and readiness |
| Native source created | **OBSERVED from operator-supplied Core readiness**: `draft` | `@clinical_trials_gov_v2`, `rt_src_421eba0e307942b781e252ba0f631691` (client/lake not in the projection) |
| Published / readiness ready | **NOT YET**: `draft` / `blocked`; only `source_published` blocked | After operator publishes, capture new source status/readiness and checks |
| Signed worker simple `query.intr` read | **NOT OBSERVED** | safe run reference, returned root/object study count, result status |
| Complex Essie/alias/cursor | **NOT PROVEN** | error code or successful safe terminal proof |
| Exact study/arms/outcomes/results reads | **NOT PROVEN** | safe NCT identity, section presence, typed result |
| Callable child and Remote MCP publication | **NOT PROVEN** | separately admitted composition/publication proof |

**Never post** credential values, authorization headers, Core encrypted config, raw provider response bodies, request target config, service keys or private execution material to this ledger. Provide only safe source IDs, counts, versions, observed status/reason codes and redacted output shape.

### Core readiness readback (operator-provided; 2026-10-17)

| Safe field | Observed state |
| --- | --- |
| Source ID / handle | `rt_src_421eba0e307942b781e252ba0f631691` / `@clinical_trials_gov_v2` |
| Kind / execution | `generic_http` / `asset_runtime_fetch` |
| Lifecycle | `status=draft`; `readiness_status=blocked` |
| Eight passing checks | `source_kind_supported`, `execution_mode_supported`, `runtime_config_present`, `request_target_present`, `response_policy_present`, `authority_ready`, `authority_execution_resolvable`, `runtime_source_node_bound` |
| Sole blocked check | `source_published` |
| Node binding | `not_required`; `required=false`; `can_bind=false` |
| Public authority | `state=ready`; `auth_scheme=public`; `vault_owner=none`; `execution_resolvable=true` |
| Resolved authority reason | `runtime_source_authority_resolved` |

**Interpretation:** Core recognizes a configured source and its public/no-node authority. The only observed readiness blocker is normal draft publication state. This readback does **not** prove the deployed Request URL, parameter allowlist, response parser/root preservation, HTTP transport, source-role mapping into Assets, successful trial search, or any provider result.

**Next operator step:** Select **Publish** for this exact source in DLM UI, then **Recheck readiness**. Record the new safe `status`, `readiness_status`, and checks before attempting an independently admitted `local_worker` trial lookup. Do not infer that publication has occurred from this snapshot.

## 5. Source anchors (current main revisions)

- UI: `apps/dlm-workspace-ui/src/js/Components/platform/mcp/McpToolConnectorCreateDrawer.vue`, `McpRuntimeSourceList.vue`, `Composables/platform/mcp/useMcpRuntimeSources.ts`
- Core: `app/Services/Platform/RuntimeSource/RuntimeSourceNodeBindingService.php`, `RuntimeSourceReadinessGate.php`, `RuntimeSourceExecutionMaterialService.php`, `config/runtime_source_execution_plan.php`, `tests/Feature/Api/Platform/RuntimeSource/RuntimeSourceOptionalLakeScopeApiTest.php`
- Assets: `python_runtime/devtools/runtime_source_v2_http.py`, `runtime_source_configured_query.py`, `runtime_source_dynamic_invocation.py`, `callable_variables.py`
- Intake: `clinical_trials_lookup.asset.json`, `clinical_trials_lookup_adapter.py`, `CAPABILITY_MATRIX.md`
- Official provider: ClinicalTrials.gov Data API documentation and `/api/v2/version` metadata.

**No Core/UI/Assets changes are requested by this document.** A real contract failure should be recorded and routed to the owning layer with one focused regression test rather than weakening safety or introducing adapter-owned transport.

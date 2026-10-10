# Full intelligence CompanyContext handoff — 0.1.14

## Objective and scope

Remove duplicate Companies acquisition when full intelligence follows Company
Scope. Add one version of the existing intelligence asset; retain all earlier
identities and the evaluation asset. Do not expand the runtime, rewrite shared
helpers, change research prompts or bypass Dynamic Skill authority.

## Grounded ownership model

| Boundary | Owner | Contract |
| --- | --- | --- |
| Selector, fixed corporate filter, Companies acquisition | Company Scope + Assets/Core binding | actual Companies field `corporate=1`; DTO `corporate_id=1` |
| Retained output access, expiry and checksum | Assets/Core | exact producer/run/output/client authorization |
| DTO validation and company isolation | Intelligence 0.1.14 | complete result, exact requested set, 1–5 records |
| Research/provider execution | existing runtime Agent helpers | unchanged eight-role graph and finite budgets |
| Memory and methodology persistence/history | Core Dynamic Skill | existing eligibility, expected digest, mutation/readback |
| Large job epochs/restarts | existing admitted runtime orchestration | separate capability; no implicit adapter loop |

Company Scope reads the lake/node. Intelligence receives CompanyContext and
never reads Companies again. Reading existing company memory/methodology through
Dynamic Skill remains necessary under its existing contract. Fixed/Dynamic
Skills share runtime capabilities; their role/selection/mutability differences
do not require another storage lane or artifact publish policy. See
[Skill lifecycle and first-package handoff](https://github.com/piusaibah/assets/blob/main/docs/observability/skill-lifecycle-and-first-package.md).

## Caller-side input

```json
{
  "company_context": {"run_uuid": "<completed authorized Scope 0.1.0 run UUID>"},
  "variables": {
    "execution_scope": "batch",
    "company_ids": [13],
    "objective": "company_intelligence_memory",
    "research_depth": "deep",
    "memory_mode": "preview",
    "publish_dossier": false
  }
}
```

Replace the UUID with an actual retained, unexpired completed Scope run. A
placeholder UUID can pass local shape checks but is not evidence of admission.
`company_ids` must equal the entire Scope result set. It controls intended target
order and guards mismatches; it does not create another query/binding.

The manifest input is `source=direct` with a `retained_output` policy pinned to
`nusaibah.company_scope:0.1.0` / `company_scope_result`. Direct describes the caller
run reference; it does not authorize callers to submit raw CompanyContext bytes.
Assets' `RetainedAssetOutputInput` validates the reference, client, producer,
completion, retention, artifact envelope, size and checksum before hydration.
Python receives `{value, provenance}` with `authority=core_artifact`. Those labels
alone are not proof of access: the trusted runtime boundary is mandatory.

## Consumer contract

The version-owned helper validates exact scope/context/source key sets, schema
versions, complete status, corporate scope, bounded positive integer IDs,
record/selector correspondence, text bounds and canonical SHA-256 digests.
Strings are producer-normalized and NUL-free. Booleans are not identifiers.
Both company and enclosing scope digests must match. It rejects partial scopes,
unknown fields, caller overrides, stale producer identities and mismatched IDs
before Fixed Skill, Agent or Dynamic Skill calls.

It projects only business fields: `company_id`, `company_name`, `corporate_id`,
`address_line1`, `address_line2`, `headquarters_country_id`, `website`,
`source_updated_at`. Provider prompts do not receive storage refs, artifact
checksums or provenance metadata. Existing bounded baseline projection still
applies to Agent input. A country ID is not converted into an invented country
name. Stored fields are observations and still need corroboration under the
existing research and critic contracts.

Failures reuse the reviewed `pharma_agent_business_schema_invalid` code with
safe generic `proof_failure_detail.v1`: `role=company_context`,
`stage=input_contract`, and a static rule. No new business-specific code is added
to shared runtime logic. Existing critic failures retain their distinct stages.

## Compatibility and test gates

The new canonical adapter changes only its version, helper imports and record
acquisition seam. All previously shared helper bytes stay unchanged. Agent
definitions, chains, Dynamic Skill bindings, fixed methodology digest and output
contracts must match the retained 0.1.13 manifest except for input roles.

Retain frozen 0.1.12 and 0.1.13 sources under tests only. Run their orchestration,
apply-safety and budget suites alongside the current candidate suite. Verify
flat and dotted packaged imports; the helper has no Adapter subclass/identity.
Run malformed handoff, digest, corporate, bounds, exact-set and no-helper-call
regressions. A full deterministic two-company run must use the existing 24 Agent
calls, preserve requested order, exclude Companies acquisition and mutate zero
records in preview. Five companies still require 60 logical preview calls.

Use Assets' official materializer against the pinned intake commit in an isolated
scratch target. Confirm prior manifest identities and versioned adapter bytes
remain intact, no shared support conflict occurs, and the new input policy is
retained. The actual official workflow validates packaged imports/catalog and
creates the Assets promotion PR. Do not hand-edit packaged adapters/catalog,
bump/install a wheel, remove prior manifest identities or overwrite Agent chains.

## Rollout order and remaining gates

1. Review and merge the focused intake PR. Promote the exact reviewed commit
   through `adapter-intake-promote-pr.yml`, targeting current Assets main with
   manifest removals disabled. Review/merge the generated promotion PR.
2. Register/admit intelligence 0.1.14 and promote its exact source/catalog into the
   E local worker using the established source transport. Keep runtime 0.1.104.
   Resolve the producer and consumer identities; verify health/ownership, Agent
   admissions, fixed/dynamic skill material, and retained-output readability.
3. Reuse a valid complete Scope 0.1.0 result with no more than five companies, or
   acquire one company through the existing governed Scope path if it expired.
   Supply its run UUID only. No downstream Companies binding is created.
4. Perform one full intelligence preview and inspect retained dossier/candidates.
   Deterministic tests do not prove live factual quality/provider success.
5. Apply only eligible reviewed candidates through the existing Dynamic Skill
   authority and verify readback/change history. First-object methodology
   creation is still not provided by this change: the existing apply guard is
   preserved and stops before either memory or methodology mutation.

Scope 0.1.1 pages and large-epoch batches need an explicitly admitted complete
batch handoff with ordering/checkpoint semantics before this consumer can use
them. Do not call a capped/partial export complete, widen the five-company
intelligence limit, or introduce a second data acquisition lane as a workaround.
No `.env` change is required by 0.1.14.

## Runtime Skill dependency compatibility — 0.1.15

The caller still supplies only `company_context` and `variables`. Assets adds
four manifest-declared Runtime Skill slots before SDK invocation:
`company_memory`, `company_memory_update`, `company_methodology`, and
`company_methodology_update`. These are dependency slots, not caller inputs or
additional Companies acquisition.

Version 0.1.14's exact two-key check rejected that legitimate six-role map before
any provider call. Version 0.1.15 preserves the two required business roles and
permits only those four optional runtime-owned names. Their values remain opaque
to CompanyContext validation and never become research evidence. SDK
`dynamic_skill(...)` retains all read/mutation authority. Unknown roles, caller
Skill overrides, raw contexts, partial scopes and digest mismatches remain
rejected. The server manifest boundary still rejects caller Skill slots with 422;
local role-name acceptance does not establish runtime authority.

Before a provider test, validate the complete runtime input map including
manifest dependency slots, not just an inputs-only fixture. Regressions cover
all slot subsets, opaque values, unknown and missing roles, the full two-company
preview with 24 Agent calls and zero mutation, real installed SDK RuntimeInputs,
and retained 0.1.12/0.1.13/0.1.14 business suites. Publish through the official
workflow. Runtime 0.1.104 and previous version/helper bytes remain unchanged.

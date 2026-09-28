# Nusaibah Bedrock Agent Capability Lab

This folder is the canonical adapter-intake source for
`nusaibah.bedrock_agent_capability_lab@0.1.2`.

It is a separate Bedrock reference asset. The existing
`nusaibah.agent_capability_lab` Vertex lineage is intentionally not modified.

## Purpose

The asset proves that a business adapter can compose governed runtime
capabilities while remaining provider-API blind. Python owns only logical
roles, bounded semantic input, deterministic validation, and bounded evidence.
Assets/Core own Agent admission, ProviderVault authority, Bedrock transport,
AWS role material, provider execution, retries/finalization, and runtime truth.

The initial version exercises:

- Bedrock logical Agent invocation through `inputs.invoke_agent(...)`;
- the manifest-pinned Fixed Skill;
- read-only Dynamic Skill company memory for canonical `company_id=13`;
- a governed callable asset;
- the Healthcare NLP runtime tool;
- Bedrock + Dynamic Skill composition;
- Bedrock + Healthcare NLP composition using aggregate counts only;
- a Bedrock-proposed mutation on the synthetic Dynamic Skill fixture
  `company_id=900013`;
- fresh-run mutation receipt/digest verification;
- a same-run full composition across Fixed Skill, Dynamic Skill, callable
  asset, Healthcare tool, and Bedrock Agent.

## Bedrock boundary

The manifest carries only reviewed safe runtime selectors/references for the
already-proven Bedrock lane. The adapter itself does not contain the Bedrock
binding, model, region, provider instance, AWS role, or credential material.

The adapter must never import or call:

- `boto3` or another AWS/provider SDK;
- OBS/DLM/Core HTTP APIs;
- ProviderVault endpoints;
- credential or signing helpers;
- storage/object APIs;
- provider-native transport.

All Bedrock execution enters through the declared logical role
`bedrock_orchestrator`.

## Search and citations

Version 0.1.2 deliberately does not claim Bedrock provider-native web search or
Vertex-style grounding. Current runtime evidence supports the reviewed
provider-grounding contract for Vertex, not Bedrock.

Bedrock response metadata may be proven through the trusted Agent result
contract, but raw provider response bodies, native transport payloads, and
credential/runtime authority must never be projected into adapter output.

## Dynamic Skill safety

Canonical company memory is read-only and partitioned by runtime variable
`company_id`.

Mutation proof is restricted to the synthetic fixed partition `900013`.
The Bedrock model proposes bounded plain text only. The adapter renders that
text as inert quoted evidence, previews the governed changeset, and commits
through the runtime-owned Dynamic Skill mutation helper with an expected
digest. Model output alone is never treated as persisted state.

## Reference comparison

| Concern | Existing capability lab | Bedrock capability lab |
| --- | --- | --- |
| Provider reference | Vertex-oriented lineage | Bedrock-only reference |
| Asset key | `nusaibah.agent_capability_lab` | `nusaibah.bedrock_agent_capability_lab` |
| Version lineage | Existing published lineage | Current correction candidate `0.1.2` |
| Agent helper | `inputs.invoke_agent(...)` | `inputs.invoke_agent(...)` |
| Fixed Skill | Governed immutable Skill | Same governed pattern |
| Dynamic Skill | Governed read/mutation patterns | Same governed pattern |
| Callable asset | Governed child asset | Same governed pattern |
| Healthcare NLP | Governed runtime tool | Same governed pattern |
| Provider search | Vertex grounding where admitted | Not claimed |
| Provider SDK in Python | Forbidden | Forbidden |

## Proof stages

- `scaffold`
- `bedrock_agent_invocation`
- `fixed_skill_read`
- `dynamic_skill_read`
- `callable_asset_api`
- `healthcare_nlp_entities`
- `bedrock_dynamic_skill_analysis`
- `bedrock_healthcare_nlp_entities`
- `bedrock_dynamic_skill_mutation`
- `dynamic_skill_commit_verify`
- `bedrock_full_composition`

Every non-scaffold run also validates the supplied `execution_plan.v1`.
The plan is developer intent only; it does not grant provider, tool, Skill,
storage, or credential authority.

## Repository ownership

- Author and review this asset in `pipharmaintelligence/adapter-intake`.
- Promote it through the existing adapter-intake workflow.
- Do not hand-edit the packaged copy in `piusaibah/assets`.
- Shared runtime defects belong in `piusaibah/assets/python_runtime`.
- ProviderVault/provider authority defects belong in DLM Core.

## Before promotion

Keep these gates separate:

1. source/manifest validation;
2. focused local tests with fake trusted helpers;
3. adapter-intake promotion plan;
4. packaged importability;
5. Agent runtime provisioning/admission;
6. live Bedrock execution;
7. optional later ECS parity.

A local fixture PASS does not prove remote provider execution.

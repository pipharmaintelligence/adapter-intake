# Nusaibah Pharma Company Intelligence Lab

Canonical adapter-intake source for `nusaibah.pharma_company_intelligence_lab`.

## Current immutable candidate

`0.1.6` is the current intake candidate. It preserves the governed company-input, published Fixed Skill, Dynamic Skill, output, and seven unchanged Agent-role contracts from `0.1.5`, while applying one scoped methodology-planner reliability change:

- methodology planner Agent contract/chain: `1.0.1 -> 1.0.2`;
- `max_tokens: 2048 -> 8192`;
- `thinking_level=medium` unchanged;
- `response_format=json_object` unchanged;
- the version-owned adapter deterministically routes the canonical research-section table of contents into section-sized planner chunks;
- benchmark coverage supplies a deterministic priority hint when one is known;
- if a section has no deterministic priority mapping, that bounded planner call may choose only low/medium/high;
- every mandatory research section is still planned exactly once;
- the planner receives only the selected section/subsection slice, section-scoped benchmark evidence, and bounded global methodology rules;
- Python deterministically merges all validated chunks into one complete methodology plan and runs the existing full-plan validator.

The other seven Agent definitions remain at contract/chain `1.0.1`.

Create a new asset version whenever adapter code, manifest metadata, reviewed helpers, dependency contract, or portable Skill bytes change. Environment-only repairs do not mutate an existing published version.

## Shared-helper coexistence

Retained published versions share the reviewed helper files in this folder. Version-specific behavior must stay in the version-owned adapter implementation unless a shared-helper migration is explicitly designed for every retained identity.

For `0.1.6`:

- `agent_contract.py` is unchanged;
- `methodology_contract.py` is unchanged;
- `input_contract.py`, `dossier_contract.py`, and `memory_contract.py` are unchanged;
- `adapter.dependencies.json` is unchanged.

This preserves the current Assets materializer coexistence contract and avoids a `shared_runtime_file_conflict`.

## Planner token-safety boundary

`max_tokens` remains a hard total-output authorization. `0.1.6` does not add hidden thinking budget, retries, provider changes, or weaker validation.

The planner receives an 8192-token hard ceiling with medium thinking, but each provider call plans only one research section. Section calls are bounded to one question, one freshness-focus item, and one evidence-focus item, each at most 280 characters.

The deterministic merge then enforces the final-plan limits:

- at most 3 questions per research role;
- at most 2 freshness-focus items per research role;
- at most 2 evidence-focus items per research role;
- at most 4 cross-cutting questions;
- at most 4 known-memory gaps;
- at most 4 expected uncertainties;
- at most 280 characters per planner prose item;
- at most 12000 serialized JSON characters in the accepted final plan.

This avoids requiring one model turn to read and plan the entire research scope. Provider output-limit termination remains a runtime failure and is never accepted as completed JSON.

## Batch and governed-input contract

The launch variable is a bounded `company_ids` array such as `[13]` or `[13, 59]`. `companies` is binding-owned and `variables` is direct.

The governed company source is:

- lake: `test_database_lake`;
- node: `companies`;
- database primary key: `id`;
- company-name column: `company`.

The approved row/data mapping is `id <- company_ids`. This is not a partition mapping.

Assets/Core resolves the governed `companies` input before Python starts. The adapter normalizes `id -> company_id` and `company -> company_name`, validates exact requested/resolved ID parity, and processes company contexts independently.

A new asset version requires its own exact governed binding identity; readiness of a `0.1.5` binding does not prove `0.1.6` binding readiness.

## Fixed Skill and Dynamic Skill

The Fixed Skill remains publication-backed:

`nusaibah.pharma-intelligence-methodology@1.0.0`

with its existing canonical digest.

Dynamic Skill roles and authority are unchanged:

- `company_memory`: read-only current company partition;
- `company_memory_update`: mutable current company partition when apply mode is explicitly used.

No Skill publication, mutation-authority, storage, or persistence behavior changes in `0.1.6`.

## Format ownership

`dossier_contract.py` owns exact section IDs, subsection IDs, titles, and order. Agents return machine IDs and content only. Titles and hierarchy are rendered deterministically by the adapter.

## Promotion ownership

This adapter-intake folder is the reviewed source package. Published Assets materialization must be produced through the pinned adapter-intake promotion workflow rather than by hand-editing the packaged Assets directory.

Promotion must preserve every already-published pharma version and must not use manifest-removal authorization.

## Live proof boundary

A green intake or promotion PR is not live proof.

After promotion/deployment of `0.1.6`, prove independently:

1. exact `0.1.6` governed Companies binding;
2. exact planner `1.0.2` Agent admission;
3. exact worker/runtime catalog identity for `0.1.6`;
4. company 13 preview;
5. benchmark reviewer completion followed by methodology planner completion;
6. remaining roles in execution order;
7. Dynamic Skill mutation separately from runtime result;
8. dossier file publication separately from runtime result.

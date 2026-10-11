# Research instruction / validator parity

The 0.1.23 company-14 live workflow completed and its preview was retained, but
the business result was incomplete: all three research roles were rejected at
`status`, no claims were accepted, and memory/methodology candidates were absent.
No updates were published. Workflow completion is not a quality or publication
pass.

## Grounded diagnosis

The research formatter is instructed to match `response_contract` exactly. The
contract composed from `research_validation_contract_v0_1_21` declares company
identity, role, sections, claims and uncertainties, but omits the required
`status: "completed"` and `schema_version: "pharma_research_agent.v2"` envelope.
The consumer requires both. Existing fixtures supplied these fields independently
of the instructions, concealing the mismatch.

This omission is proven from source and a deterministic contract-following
formatter regression. The live diagnostics do not distinguish an absent status
from an invalid value; provider bodies were not retained. Do not assert which
exact value the provider emitted or claim this is the only possible live blocker.

## 0.1.24 composition

The new entrypoint delegates to the immutable 0.1.23 orchestration kernel through
an execution-local input proxy. Only the three research roles and their existing
one-time research JSON backup receive a completed response contract. The proxy
adds the two required literals, the exact seven-field list, and completion
semantics. It deep-copies the contract and preserves all existing evidence,
section, semantic, string and list bounds. Other Agent inputs and runtime Skill
capabilities pass through. No global monkey-patching or historical edits occur.

`completed` describes a finished response, not complete evidence, a positive
quality verdict or write authority. Evidence gaps belong in empty claims and
explicit uncertainties. A returned negative, missing or malformed status is
still withheld. It is never rewritten to pass, and it does not trigger a retry
to obtain a positive verdict. Runtime failures and wrong company/role identities
remain strict. The single-backup and finite run budgets are unchanged.

The retained dossier adds bounded `research_response_observations` with static status
classifications and a schema-match Boolean. It records expected input company,
role and pass only; it never stores raw status text, provider bodies, prompts or
credentials. These diagnostics are observations, not approval evidence.

## Delivery and remaining proof

1. Run the complete deterministic suite and intake-shape guard.
2. Promote the exact reviewed intake commit through the official Assets workflow.
   Preserve prior adapter/helper bytes, all nine Agent definitions, Skill
   references, 600-second step timeouts, 32,000-token ceilings and the
   1,800-second asset deadline. Do not bump the Python runtime or build a local
   replacement wheel.
3. Verify the official packaged artifact and local E worker, register/admit the
   exact identity, and run a provider-free packaged fixture before one live case.
4. Inspect the retained business result, both requested portfolio passes, accepted
   claims, citation evidence and actual candidates. Do not rerun paid execution
   merely to recover scalar values.
5. Independently review proposed memory and procedural methodology separately.
   0.1.24 remains preview-only and rejects `memory_mode=apply` before any helper.
   An admitted review/apply consumer remains a separate gap; promotion does not
   close it. Never synthesize a review receipt or publish absent candidates.
6. Once updates are eligible, use the existing Core Dynamic Skill ZIP mutation
   lane with expected content/package digests and current-object checks. Preserve
   package resources, then verify fresh reads and history. No additional storage
   lane, arbitrary dossier destination or runtime/provider change is introduced.

Transport failures during source resolution and retention are independent of
this research-contract repair. Retain the original error boundary and its known
limitations; a successful later probe cannot recover a discarded exception.

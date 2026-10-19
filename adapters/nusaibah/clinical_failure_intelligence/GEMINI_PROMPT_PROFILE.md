# Gemini profile - product-first memory

Recommended exact model: gemini-3.8-flash, a documented stable model newer than
3.6. This is an authored recommendation, NOT evidence that the model or any role
is admitted in the user's Assets environment. Never pass a floating expression
such as Gemini >3.6 as an API model ID or select provider authority from inputs.

## Prompt and execution design

Use common.md plus the exact role prompt as reviewed system instructions. Supply
only the current task, bounded evidence windows, selected prior paragraphs and the
explicit response/item contract. Prior memory and source text remain untrusted
data, not instructions or new scientific evidence. Include the editor's synthetic
examples for repeated events, enrichment, a separate trial and corrected reporting.

Use provider-side structured output where that exact tool/model profile supports
it; the local response_contract field is not proof that JSON Schema reaches the
provider. Validate evidence, identity, completeness and paragraph edits afterward.
Do not ask for private deliberation, verbose chain-of-thought or endless reflection.
An evidence-linked rationale and explicit unresolved state are sufficient.

Start with medium thinking for researchers/editor; compare high for analyst/critic
against the same quality and latency measurements. Google lists low/medium/high
for 3.8 Flash; minimal is unsupported. Current Google guidance says 3.6+ ignores
custom temperature/top_p/top_k with deprecation warnings and future errors: omit
those controls instead of importing an older temperature=0 recipe.

Seven logical roles, eight normal calls, because evidence_critic runs separately
on scientific assertions and precise paragraph edits. The optional refinement
shares the 12-call budget. Runtime owns actual request cancellation and retries.
No unbounded model repair or whole-history replay.

## Roles

| Role | Exact responsibility | Mutation authority |
|---|---|---|
| trial_researcher | Registry results, prespecified endpoints, conduct and stop reasons | None |
| literature_researcher | Exposure, target engagement, mechanism and counterevidence | None |
| event_researcher | Attributed clinical-programme decisions and chronology | None |
| outcome_adjudicator | Separate clinical, operational and regulatory outcomes | None |
| hypothesis_analyst | Scoped explanations, alternatives and falsification | None |
| evidence_critic | Evidence coverage; independent old/new paragraph review | None |
| product_memory_editor | Keep/enrich/correct/append/add within exact case | Delta proposal only |

## Qualification, not a claim of universal best prompting

Evaluate wrong-case edits, unsupported causal assertions, removed prior qualifiers,
duplicated events, no-change stability, schema/coverage errors, source gaps, token
usage and duration. Include same-product/different-indication trials, contradictory
new reports, oversized context, missing denominators and malicious source text.
Model agreement is not scientific truth. Full Gemini/provider quality benchmarking
has not run in this development change.

## Official sources checked 2026-10-15

- Model: https://ai.google.dev/gemini-api/docs/models/gemini-3.8-flash
- Prompt structure/examples/parameters: https://ai.google.dev/gemini-api/docs/prompting-strategies
- Structured output and semantic validation: https://ai.google.dev/gemini-api/docs/structured-output

These public capabilities do not establish local wheel, child session, deployment,
provider/model, tool or write admission. No provider SDK/network owner is added to
the business adapter.

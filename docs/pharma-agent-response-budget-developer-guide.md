# Pharma Agent response budgets and thinking headroom

## Objective

Prepare compact, complete role responses within provider generation limits while
preserving the existing evidence, independent-review and publication boundaries.
Deliver asset `nusaibah.pharma_company_intelligence_lab:0.1.22` through official
promotion without changing the runtime version or previously promoted identities.

## Proven failure boundary

On 2026-10-11, Company Scope run
`4adaa057-16aa-40a9-b63d-91285951f8d9` completed for company 14 through the governed
Companies binding. The fresh CompanyContext was passed directly to intelligence;
the intelligence adapter did not re-query Companies. Existing Fixed Skill,
company memory and optional company methodology reads passed.

Intelligence run `4a32596d-28d8-4d2e-826b-30690e45f4cb`, asset 0.1.21, failed at
the first research/search step. Each researcher used an 8,192-token ceiling;
Vertex returned HTTP 200 with `finish_reason=MAX_TOKENS`, mapped to
`provider_execution_output_limit_reached`. No reflection, completed dossier or
new memory/methodology publication resulted from this run.

| Role | Prompt tokens | Answer tokens | Thinking tokens | Total tokens |
| --- | ---: | ---: | ---: | ---: |
| market_researcher | 4,979 | 1,820 | 6,628 | 13,427 |
| regulatory_risk_researcher | 5,013 | 326 | 8,467 | 13,806 |
| portfolio_researcher | 5,295 | 326 | 9,232 | 14,853 |

These are the provider usage fields recorded for the failed steps, not an
independently reconciled billing total. Thinking used substantial capacity even
where the visible answer was short. Retrying the unchanged 0.1.21 declaration
would repeat the same bounded generation problem.

## How the controls work

1. The role prompt guides visible answer size and relevance. The existing
   response contract remains authoritative for required IDs, fields, array counts,
   evidence qualifiers and tighter character limits.
2. The provider policy sets `max_tokens=32000` on all 12 steps. The generic Vertex
   transport maps this to `maxOutputTokens`; generation, including thinking,
   remains bounded by provider behavior.
3. The deterministic parser and business validator check the returned response.
   A size target cannot excuse incomplete JSON, fabricated citations or a changed
   negative verdict. The existing one-time faithful format resolver is unchanged.
4. Assets retains completed preview evidence; Core remains the sole Skill storage
   and history authority. Neither response-size guidance nor automated quality
   approval establishes independent source review or publication permission.

The prompt is guidance, not a second hard token meter. It cannot control thinking
tokens precisely. Google documents the interaction between thinking and output
limits in [Thinking](https://ai.google.dev/gemini-api/docs/thinking), and defines
`MAX_TOKENS` in the [Vertex GenerateContentResponse contract](https://cloud.google.com/vertex-ai/generative-ai/docs/reference/rest/v1/GenerateContentResponse).
The framework currently admits at most 32,000 requested generation tokens. Do not
silently request a higher value that Core/Assets would normalize or reject.

## Role budgets

The packaged `pharma_response_budgets_v0_1_22.json` records these advisory visible
character targets. A token is not a character; no fixed conversion is assumed.
All rows use the same 32,000-token provider ceiling.

| Role | Fresh contract | Visible character target per step |
| --- | --- | --- |
| methodology_planner | 1.0.8 | 4,500 |
| portfolio_researcher | 1.0.9 | 12,000 search; 26,000 JSON |
| market_researcher | 1.0.9 | 12,000 search; 26,000 JSON |
| regulatory_risk_researcher | 1.0.9 | 12,000 search; 26,000 JSON |
| strategic_analyst | 1.0.6 | 18,000 |
| evidence_critic | 1.0.9 | 20,000 |
| intelligence_synthesizer | 1.0.7 | 32,000 |
| memory_benchmark_reviewer | 1.0.5 | 6,000 |
| research_response_resolver | 1.0.4 | 33,000, subordinate to faithful preservation |

Targets permit required bounded payloads; they do not enlarge the typed business
contract. For JSON steps, the prompt requests every required field and closing
brace, no Markdown, no deliberation, no context restatement, and no repetition.
For search steps, it requests relevant concise evidence notes using the existing
grounding capability. Optional uncertainty/no-evidence fields retain their
existing meanings. The resolver cannot drop records or change facts to fit.

## Compatibility and delivery

The new 0.1.22 entrypoint delegates to `invoke_v0_1_21` with its new asset identity.
The 0.1.21 kernel, helpers and entrypoint are unchanged. Historical tests retain
their original 0.1.21 metadata fixture; separate current-release tests check the
new declaration. Previously reference-only roles embed their exact previously
admitted definitions with only the new version, generation ceiling and appended
budget guidance changed.

All models, thinking levels, vault references, search/citation authority, safety
policies, maximum provider/tool calls, 600-second requests, and the 1,800-second
total deadline stay intact. All business inputs, outputs, Fixed/Dynamic Skill
references and dry-run contracts stay intact. No generic Core/Assets runtime code
or upload lane changes are part of this repair.

1. Run the complete deterministic pharma suite and intake contract validation.
2. Verify declared module/support closure and historical runtime identities using
   the official materialization and packaged-catalog checks.
3. Promote the exact intake commit with the existing promotion workflow. Review
   and merge the intake and Assets promotion PRs in order.
4. Obtain the verified artifact from merged-main CI. Keep runtime version
   `0.1.105`; do not build a local replacement wheel.
5. Verify installed file hashes, catalog identities, registration, all nine fresh
   Agent contracts, Core's provider-policy ceiling, and the expected E local worker
   before a new paid launch.
6. Run one guarded company-14 preview with two total portfolio passes. Inspect
   actual usage, finish reasons, retained claims and independent review evidence.
   Do not automatically loop paid launches after a failure.

The inspected local Core policy currently permits 16,384 output tokens. An
unchanged policy would reject the new 32,000-token request before any provider
call. Use the existing scoped `dlm:provider-execution-policy-update` command;
identify the exact current registration and owner from the governed runtime
authority. Dry-run first, leaving `--apply` omitted:

```powershell
php artisan dlm:provider-execution-policy-update `
    --registration-id=$RegistrationId `
    --owner-integration-id=$OwnerIntegrationId `
    --client-id=$ClientId `
    --provider-family=vertex_ai `
    --provider-instance=vertex-primary `
    --capability=llm.generate `
    --max-output-tokens=32000
```

The local dry-run passed with only `max_output_tokens` changing from 16,384 to
32,000. Input limits, timeout, thinking/search permissions, availability scope and
selector metadata stayed intact. Apply the reviewed update through this same
command when activating the release. It changes the allowed ceiling for that
registration; existing assets retain their own requested generation budgets.
Read back the policy and require the actual admitted slots to retain 32,000 before
spending on the next run. No `.env` editing or Core code change is needed.

## Limits and publication requirements

A 32,000-token ceiling may increase provider cost, memory use and latency; the
compact prompts aim to reduce unnecessary visible output. It is a maximum, not a
target or fixed charge. Measure actual usage in the next run. A larger ceiling
does not extend the total execution deadline, increase concurrency, or guarantee
that every company finishes within 30 minutes.

0.1.22 remains preview-only. `memory_mode=apply` raises
`pharma_independent_review_required` before Agent or Skill calls. Its review packet
does not carry apply authority. A successful preview is a candidate for independent
review, not proof that it is published. Updating existing memory/methodology must
use their existing Core-authorized Skill mutation/history capabilities after
review, preserve package resources and baseline digests, and verify readback.
Failed/truncated output cannot be transformed into an approved publication.

# Nusaibah Agent Capability Lab

This folder is the canonical adapter-intake source for `nusaibah.agent_capability_lab`.
Assets packaging must be produced through the adapter-intake promotion workflow; do not
hand-edit a published packaged adapter in `piusaibah/assets`.

## Strict model-output contracts

The grounded Vertex certification stage uses a deliberately strict line-oriented protocol.
It is not a generic Markdown parser.

Current grammar:

```text
FORMAT_ID: capability_lab.vertex_grounded.v1
SUMMARY:
- <summary item 1>
- <summary item 2>
VERIFIED_UPDATES:
- <verified update 1>
- <verified update 2>
MEMORY_NOTE:
<concise evidence-based non-bullet note>
END_FORMAT
```

Normative rules:

- `SUMMARY` contains 2–4 items.
- `VERIFIED_UPDATES` contains 2–6 items.
- Every item is exactly one physical line.
- Every item begins with the exact ASCII prefix `- ` (hyphen + one space).
- `* `, `+ `, numbered bullets, continuation lines, and extra non-bullet lines are rejected.
- `MEMORY_NOTE` is non-bullet prose.
- The opening `FORMAT_ID`, section labels, section order, and final `END_FORMAT` marker are exact.

## Lesson learned: prompt grammar and validator grammar are one contract

A provider call can complete successfully and still fail certification when prompt wording
describes a broader format than the validator accepts. In the 0.1.13 lineage, the prompt
said “Markdown bullet lines” while the validator accepted only `- ` lines. Both behaviors
were individually reasonable, but together they formed an inconsistent adapter contract.

Future development rule:

1. Define strict grammar with shared constants before writing prose instructions.
2. Make prompt wording no broader than the validator.
3. Include a minimum valid template in the provider-facing instructions.
4. Keep positive and negative tests beside the versioned adapter source.
5. Test alternative syntax explicitly (`* `, `+ `, wrapping, count boundaries).
6. When grammar changes, bump the adapter version; do not mutate an already-published identity.
7. Update instructions, validator, tests, docstrings, and this README in the same change.
8. If a live proof fails, separate provider completion from downstream adapter validation before
   changing model, timeout, credentials, runtime, or token budget.

## Diagnostic discipline

For strict-output failures, preserve bounded evidence such as the failed rule, counts, and fixed
classifications. Do not retain raw model output merely to debug formatting. Provider completion
evidence and adapter proof-stage evidence should remain separate so a completed provider call is
not misdiagnosed as a transport or inference failure.

## Repository ownership

- Local authoring and version changes belong in this adapter-intake folder.
- Shared runtime behavior belongs in `piusaibah/assets/python_runtime`.
- Promotion materializes reviewed intake files into Assets and regenerates package/catalog evidence.
- Credentials, provider secrets, storage paths, raw provider payloads, and raw OBS/Core responses
  never belong in adapter code, README examples, fixtures, or committed IDE configuration.

## Before promotion

Verify the exact adapter root with the selected project interpreter, then run the documented
adapter-intake validation and promotion-plan commands. Keep local readiness, intake readiness,
packaged importability, remote Agent admission, and live certification as separate proof stages.

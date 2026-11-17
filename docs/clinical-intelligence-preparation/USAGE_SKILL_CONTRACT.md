# Clinical Gateway usage Skill — design contract

Status: **design only, 9 November 2026**. No runnable gateway, Skill package,
`SKILL.md`, runtime declaration, MCP publication or host installation is added.
P1 remains unverified; this independent P0 contract does not require live data.

## Two separate instruction audiences

| Contract | Audience and responsibility | Identity / status |
| --- | --- | --- |
| Gateway usage Skill | ChatGPT: choose an operation, supply semantic arguments, check prerequisites and explain accepted/blocked/partial results | Proposed `nusaibah.clinical-intelligence-gateway-usage@1.0.0` |
| Scientific methodology Skill | Internal clinical runtime/Agents: evidence evaluation and scientific reasoning under admitted specialist roles | Existing `nusaibah.clinical-failure-methodology@1.1.0`; unchanged |
| Future neutral/class methodologies | Their independently admitted specialists | Exact governed references must be selected and qualified separately; not invented by this usage contract |

The active Clinical Failure Intelligence 0.1.16 manifest declares the internal
methodology digest
`sha256:9821240824bbd5b637e928d730745d5c9409f833707e48a277197bd9d6cc9ec9`.
That declaration permits the admitted runtime's fixed view; it does not expose
the methodology or install instructions in ChatGPT.

## Exact proposed usage identity and immutability

`gateway-usage.contract.json` pins the proposed Fixed Skill reference and exact
version `1.0.0`. Its digest is deliberately **null/unsealed**, not a fabricated
release hash. All seven text sections have `approval_state: draft`; runtime
admission, publication and installation are explicitly false.

Before release, review the text/audience, build the real Fixed Skill package
through the existing process and seal its exact manifest/package identity.
Do not substitute a returned section's text digest for the canonical Skill
digest. A published reference/version/digest is immutable; later content changes
require a separately reviewed version. Never request `latest` or silently fall
back to a different version. Nothing here declares 1.0.0 already published.

## Two future delivery modes; one gateway Asset

1. **Approved gateway sections.** The future gateway reads only its exact
   declared usage Fixed Skill through the existing `inputs.skill()` view and
   returns the audience-approved section. Reuse existing fixed-view identity,
   size and safe projection behavior; do not add an API client, storage reader
   or scheduler. Reusing the separately packaged generic Skill Reader as an
   internal child would require its own admitted child contract and scope;
   this preparation does not assume that composition is available.
2. **Separate ChatGPT-facing package.** A later reviewed host Skill package may
   carry the same usage instructions and exact version/digest. Host packaging,
   installation and compatibility testing are separate release work. A tool
   response does not install a host Skill. Compare installed guidance against
   the server's version/digest; stale guidance must not override current
   admission, tool schema or authorization.

Both modes preserve one future published clinical Asset,
`nusaibah.clinical_intelligence_gateway`. They do not require publicly exposing
another clinical Asset or publishing the generic Skill Reader for this task.
Returning guidance and installing a host package are distinct deliverables.

## Bootstrap and operation-specific consumption

Before a Skill is read, future tool metadata must already explain the user job,
the guidance entry point and essential limits. An example discovery description
is: “Learn which clinical review operations are available and what they need.
Read the relevant usage section before an unfamiliar operation. Guidance does
not authorize research or writes.” This is proposed text, not live metadata.

Use current, matching installed guidance when available. Otherwise, describe
capabilities and read the smallest relevant approved section. Do not repeatedly
download the whole instruction set for every status poll.

| Operation in the shared request schema | Usage section / information ChatGPT needs first | Server-owned prerequisite |
| --- | --- | --- |
| `describe_capabilities` | `overview`; learn supported operations and unavailable reasons | Caller/surface scope and approved catalog projection |
| `read_guidance` | Exact allowlisted `section_id`; no arbitrary Skill selector | Exact sealed usage identity, audience approval and current read authority |
| `request_assessment`, `existing_review` mode | `existing_review`; objective/date, semantic assessment/product reference where known | Exact retained assessment, lineage, read horizon and consumer input authority; P1 |
| `request_assessment`, `neutral_assessment` mode | `neutral_assessment`; objective/date and known product/molecule selectors; missing failure is not success | PI-1751 engine/ruleset/source admission and bounded budgets |
| `request_assessment`, `class_review` mode | `class_review`; explicit all-known/subset mode and eligible semantic selection | Frozen governed inventory/cases, no overflow/truncation, admitted product join/synthesis/critic |
| `get_status` | `get_status`; use the accepted server-issued `run_ref` | Scoped durable status projection; never re-launch because of a timeout |
| `get_result` | `get_result` plus `result_states`; preserve coverage and scientific limits | Authorized retained readback, expiry/integrity and bounded result projection |

All modes use the existing operation names and argument schemas; no additional
product-specific endpoint or arbitrary rule/execution selector is introduced.
`result_states` explains six independent completeness dimensions and the
structural meaning of handoff acceptance. The other sections are routing and
interpretation guidance, not scientific assessment rules.

## `describe_capabilities` / `read_guidance` projections

The shared request/response schemas now reference
`gateway-guidance.schema.json`. These are proposed read operations on the same
future gateway; they are not registered tools or working endpoints.

`describe_capabilities` returns a bounded catalog: operation/mode, required
argument names, safe prerequisite codes, the relevant usage section, scope
modes and exact usage identity. Every capability is `not_admitted` in the
persisted design example. Availability in a later implementation is computed
from current server authority, not copied from a model response or static
Skill. A compact argument summary never overrides the actual MCP input schema.

`read_guidance` accepts one of seven section IDs: `overview`, `existing_review`,
`neutral_assessment`, `class_review`, `get_status`, `get_result`, `result_states`.
No caller Skill reference/version, partition, resource/path/URL, tenant, actor,
binding, provider or approval selector is accepted. It returns exact approved
text, reference/version/digest, UTF-8 byte count and completeness. Ready text
requires a real sealed identity and audience approval, rechecked at read time.

Limits are **8 KiB UTF-8 per section and 16 KiB for the entire guidance
response**, further bounded by any smaller actual publication budget. These
are proposed ceilings, not deployed settings. Never truncate an oversized or
partially resolved section. Return blocked with no text when unsealed,
unadmitted, unavailable, mismatched, revoked, unauthorized or over budget.
There is no fallback to another Skill, full document or internal methodology.
Public responses expose neither provider/source data nor raw internal Skill
content. The stored blocked example contains a null digest and no text.

The gateway may eventually expose guidance independently of clinical execution
readiness, after guidance's own admission. A failed P1 clinical read does not
prevent design work or justify claiming that clinical operations are available.

## Authorization, metadata and instruction boundaries

Guidance communicates supported usage; it cannot grant lake/node access,
provider spend, output placement, reviewer admission, Skill mutation or a paid
retry. Retain current OAuth/caller/surface/publication checks, source and Skill
revocation checks, exact role scopes and response sanitization. Nothing in
returned or installed text overrides the user's intent or host instructions.

The custom `read_only` field describes operation behavior; it is not a new
authorization mechanism. A future standalone guidance/status/result MCP tool
can claim read-only only when its actual behavior is read-only. Starting a
recorded assessment creates work/state and must not be labeled read-only just
because its scientific sources are reads. If one MCP tool dispatches both
reads and starts, its annotation must cover its state-changing behavior.
This follows the [official tool-design guidance](https://developers.openai.com/plugins/plan/tools).

Keep the essential bootstrap description short and make tool sequencing
explicit in future metadata/server instructions, following [OpenAI's custom MCP
guidance](https://developers.openai.com/api/docs/guides/custom-mcp-server).
These are design inputs, not proof of installation or actual ChatGPT behavior.

## Evidence, validation and release gates

Reuse the [generic Skill Reader development proof](https://github.com/piusaibah/assets/blob/main/docs/observability/generic-skill-reader-development-proof-2026-10-13.md)
and packaged `nusaibah.skill_reader@0.1.1` behavior as evidence of approved
bounded text reads. The development proof and [Assets PR #579](https://github.com/piusaibah/assets/pull/579)
do not certify this gateway, its future Skill or an actual ChatGPT connection.

Offline checks cover identity/version separation, null/unsealed draft identity,
section allowlists, arbitrary selector/authority rejection, exact UTF-8 budgets,
blocked/no-text behavior, route/side-effect metadata and non-release flags.
Only synthetic tests construct a sealed-looking identity to exercise the ready
shape; no persisted example invents a release digest or successful guidance read.

Later release gates remain: content/audience sign-off, real sealed package,
exact admitted gateway Skill declaration, per-operation publication and budgets,
negative scope/revocation/drift tests, optional host package installation, and a
fresh ChatGPT session proving discovery, section read, operation selection,
blocked/partial handling and authorized follow-up. Clinical operations retain
their P1–P7 dependencies. No gateway execution, installation or publication is
performed by this design change.

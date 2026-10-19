# Clinical Failure Intelligence 0.1.1

PI-2061. Development implementation, not a live-ready or promoted asset.
The existing pharma evaluation and company-intelligence packages are unchanged.

## Working chain

One mechanistic_case or cohort_pattern request follows:

    governed context validation + Fixed methodology + primary product memory
    -> trial / literature / event researchers (two concurrent tasks)
    -> outcome adjudication -> hypothesis analysis -> evidence critic
    -> at most one focused refinement
    -> product memory editor -> paragraph edit critic
    -> canonical JSON + reason graph + readable report + product delta preview
    -> optional class candidate preview (disabled by default)

Seven declared roles call inputs.invoke_agent. Python owns identities, deterministic
counts, exact-source windows, scope, coverage, dependencies, graph and output.
Prompt source files are in prompts/. Agent references and their hashes are listed
in admission_requirements.json. They are not already registered or admitted roles.
No provider model, shared registry metadata, lake or node is copied from pharma.

## Evidence and safety boundary

Research uses existing clinical_context source windows and the optional binding-owned
clinical_evidence bundle. source_bundle.py consumes normalized ClinicalTrials.gov,
PubMed and UMLS results without calling or importing their adapters. Missing source
families may use the existing provider-grounded discovery and trusted HTTP path;
model-authored URLs are not admitted as evidence. The source adapters, their live
validation and runtime handoff remain separate work.
Accepted means automated support assessment inside the supplied snapshot, not
independently verified clinical truth. A literal passage match is not entailment.

The bundled Fixed Skill has an exact digest. product_memory is the primary read-only helper
use, selected by product_id; its approved node/partition declaration is pending.
case_scope preserves canonical indication/trial/regimen identities. Missing trials
remain event-scoped, not invented NCTs. Mixed trial memory work must be split by the
parent; unresolved multi-product attribution defers product-memory changes. memory_mode=off
skips it. Only the exact dynamic_skill_not_initialized error permits empty first-run
memory; missing node or authority fails closed. memory_mode=apply fails before any
Agent or Skill call. Preview does not initialize or publish anything.

The manifest requires variables (direct) and clinical_context (binding), with an
optional clinical_evidence (binding) role. Local
fixture values are not a bypass for binding-owned live input. It declares only
local_worker; callable eligibility does not prove child capabilities are installed.
No nested callable, direct provider HTTP, credentials, queue or publisher is added.

## Local verification in DataSpell

Open this asset folder as the project root. Select your actual project interpreter.
Create a Unittest configuration targeting tests. Debug one test method at a time.
Do not add the Assets checkout to PYTHONPATH or modify the installed wheel.

    python -m unittest discover -s tests -p "test_*.py" -v
    python tests/run_fixture.py mechanistic_case
    python tests/run_fixture.py cohort_pattern
    python tests/run_fixture.py prepared_evidence_preflight

The fixture runner uses explicitly synthetic doubles, not OBS or a provider. The
production entrypoint requires the real runtime package. Only import-closure tests
stub Adapter; no production stub or silent SDK fallback exists.

## Layout

contracts.py: closed input and result primitives.
policies.py / runtime_access.py: budgets, typed results and in-flight task reuse.
evidence.py / cohort.py: exact source windows and descriptive cohort denominators.
quality.py: candidate scopes, complete critic obligations and dependency invalidation.
orchestration.py: bounded role chain and focused refinement.
product_memory.py: bounded case-paragraph reads, edit review and non-applying SDK compiler.
memory.py: Fixed methodology, optional class snapshot and guarded commit boundary.
rendering.py: one deterministic graph/report from canonical assertions.

## Deliberate limits

Twelve shared Agent calls, two concurrent researchers, one refinement, an 1800-second
budget and a 120-second completion reserve. Transport retries and actual request
cancellation remain runtime-owned. Eight normal calls can become twelve after refinement.
Oversize downstream packets defer explicitly rather than truncate content.

response_repair.md is a reserved prompt, not an active Agent. The reference-read
budget covers the trusted HTTP path; source adapter calls are not made by this child.
A typed SDK output-limit failure withholds its stage without a paid retry.
There is no paid planner, inferential statistics, graph database or custom checkpoint.
Same-run reuse is not restart recovery. Persistence is explicitly not_attested.
Thirteen source-hypothesis indices are provided; they are not a gold dataset or full
PDF transcription. CHECKLIST.md distinguishes implementation from remaining work.

## Product-first revision

See PRODUCT_MEMORY_REVISION.md for exact before/after and remaining runtime gates.
See tests/reference/GEMINI_PROMPT_PROFILE.md for the model research notes. These development references do not select or admit a provider model.
Class true currently produces candidate references, not cross-product synthesis.
Product edits remain preview plans, not writes. Legacy unindexed documents defer
for migration instead of being treated as empty.

## Prepared evidence and reliability additions (same 0.1.1 draft)

See PREPARED_EVIDENCE_CONTRACT.md for the exact handoff and scientific gates, and
INTAKE_IMPLEMENTATION_CHECKLIST.md for implementation versus external validation.
The source adapters, Assets, Core, UI, selected wheel and provider settings are not
changed by this consumer slice. No new asset version is introduced.

source_bundle.py normalizes prepared source results and preserves provenance,
NCT/PMID/CUI roles, date precision, article notices and complete source windows.
review_packets.py splits focused critics without changing original validators.
decision_outcome.py adds a scientific/business disposition and independent
non-writing memory decision. Optional presentation compaction never truncates
canonical evidence or the reviewed product-memory delta.

Set preflight_only=true for zero-Agent/zero-Skill contract inspection; this does
not prove a live binding. supplementary_search=false disables the optional HTTP
fallback when testing the prepared-data path. Source plans describe unexecuted
needs only. Canonical oversize, live handoff, actual SDK, product writes and durable
restart recovery remain independently qualified gates.

# Clinical Failure Intelligence 0.1.0

PI-2061. Development implementation, not a live-ready or promoted asset.
The existing pharma evaluation and company-intelligence packages are unchanged.

## Working chain

One mechanistic_case or cohort_pattern request follows:

    governed context validation + Fixed methodology + optional group memory
    -> trial / literature / event researchers (two concurrent tasks)
    -> outcome adjudication -> hypothesis analysis -> evidence critic
    -> at most one focused refinement
    -> canonical JSON + reason graph + readable report + learning preview

Six declared roles call inputs.invoke_agent. Python owns identities, deterministic
counts, exact-source windows, scope, coverage, dependencies, graph and output.
Prompt source files are in prompts/. Agent references and their hashes are listed
in admission_requirements.json. They are not already registered or admitted roles.
No provider model, shared registry metadata, lake or node is copied from pharma.

## Evidence and safety boundary

Current research operates on source windows already in the governed clinical_context.
It does not admit model-authored URLs or invent retrieved documents. New registry,
PubMed and native-search retrieval needs the A3 integration in ASSETS_HANDOFF.md.
Accepted means automated support assessment inside the supplied snapshot, not
independently verified clinical truth. A literal passage match is not entailment.

The bundled Fixed Skill has an exact digest. group_memory is a read-only helper
use whose approved node/partition declaration is still pending. memory_mode=off
skips it. Only the exact dynamic_skill_not_initialized error permits empty first-run
memory; missing node or authority fails closed. memory_mode=apply fails before any
Agent or Skill call. Preview does not initialize or publish anything.

The manifest requires variables (direct) and clinical_context (binding). Local
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

The fixture runner uses explicitly synthetic doubles, not OBS or a provider. The
production entrypoint requires the real runtime package. Only import-closure tests
stub Adapter; no production stub or silent SDK fallback exists.

## Layout

contracts.py: closed input and result primitives.
policies.py / runtime_access.py: budgets, typed results and in-flight task reuse.
evidence.py / cohort.py: exact source windows and descriptive cohort denominators.
quality.py: candidate scopes, complete critic obligations and dependency invalidation.
orchestration.py: bounded role chain and focused refinement.
memory.py: read-only snapshot and non-writing qualified lesson proposals.
rendering.py: one deterministic graph/report from canonical assertions.

## Deliberate limits

Twelve shared Agent calls, two concurrent researchers, one refinement, an 1800-second
budget and a 120-second completion reserve. Transport retries and actual request
cancellation remain runtime-owned. Six normal calls can become ten after refinement.
Oversize downstream packets defer explicitly rather than truncate content.

response_repair.md is a reserved prompt, not an active seventh Agent. The reference
read counter is reserved; no public reference reader is connected in this release.
There is no paid planner, inferential statistics, graph database or custom checkpoint.
Same-run reuse is not restart recovery. Persistence is explicitly not_attested.
Thirteen source-hypothesis indices are provided; they are not a gold dataset or full
PDF transcription. CHECKLIST.md distinguishes implementation from remaining work.

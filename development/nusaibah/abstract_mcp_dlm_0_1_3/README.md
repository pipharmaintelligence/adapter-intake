# DLM Lake Memory 0.1.3 - development candidate, NOT registered

This is executable adapter business logic for the PI-2047 lake-memory design,
not a new platform service and not an active intake release. Existing
`adapters/nusaibah/abstract_mcp_dlm` manifest, descriptor and immutable sources
remain unchanged. This directory is deliberately outside automatic adapter
intake discovery until the exact receiving-authority binding exists.

## Implemented here

- Closed JSON request, assertion, node-plan and observation schemas.
- Client/lake/kind identity checks; no caller tenant, actor or storage overrides.
- Knowledge section/assertion upserts with retained supersession.
- One node-plan register; proposed/observed schema separation, stable IDs,
  dependencies, evidence, approval invalidation, verified completion and drift.
- Default preview, reviewed proposal/base digests, update-only expected-digest
  guard, explicit first initialization admission, no blind mutation retries.
- Existing `RuntimeInputs.dynamic_skill`, `initialize_dynamic_skill`, structural
  SkillChangeSet preview/apply and governed history interfaces only.
- Bounded context/detail/history projections and truthful persistence outcomes.
- Fixed ChatGPT workflow in `plugins/dms-dlm-discovery`, version 1.3.0.

The two memory kinds each use a complete ZIP revision maintained by the existing
trusted runtime. Business records live in one JSON block under `SKILL.md`'s State
section. The seven knowledge sections are logical JSON records, not separate
physical nodes/files. The adapter never owns ZIP delivery, credentials, network,
storage placement, output publishing, queues or real node creation.

## Deliberate integration stop

`context.dlm_lake_memory_scope` is a **proposed server-only projection**. It is NOT
an existing SDK field and must not be installed by a model, fixture masquerading
as production, public API arguments, or a generic variables bag. The candidate
fails before reading memory when it is absent. A valid-shaped dictionary is not
authentication. Assets must derive it from verified receiving authority, bind the
read/update roles to the same exact partition, and preserve signed scope and
revocation checks through execution. Core must independently authorize the
subject lake and memory partition, including ordinary object/history routes.

The partition is `client_id + lake_id + memory_kind`. The business client is not
the OAuth application ID, company record ID or subject lake owner's client.
Roles are `lake_knowledge`, `lake_engineering` (read) and their `_update` aliases
(mutable). Calls pass no selector variables; trusted runtime prebinding is required.

`dlm_node_implementation` / `dlm.nodes.implementation` and its
`dlm_node_implementation.v1` result are **pending reviewed projections**, not an
already admitted Core tool. This consumer rejects missing, cached, mismatched or
incomplete evidence. It cannot manufacture an approval or acceptance check.

Read-only package roles may currently expose `history_scope=current_resolution`.
That correctly returns `history_unavailable`. Qualify a least-privilege committed
history read path; do not give an ordinary reader mutation rights merely to read
history. The fake tests exercise both current-only and admitted-history views.

V1 requires `visibility=complete_authorized_lake`: partially authorized views fail
closed rather than filtering arbitrary prose unsafely. The shared-memory writer
must never rewrite a package using only a restricted partial view.

## Run and inspect in DataSpell

Open adapter-intake as the project root and select a Python 3.10+ environment with
`jsonschema`. Add a unittest run configuration for `tests/test_dlm_lake_memory.py`.
The fake tests need no credentials or network. The candidate imports only its own
helpers. The thin 0.1.3 wrapper additionally reuses unchanged 0.1.2/0.1.1 modules
from the existing adapter root when assembled for a future release.

```sh
python -m unittest discover -s tests -p test_dlm_lake_memory.py -v
python development/nusaibah/abstract_mcp_dlm_0_1_3/export_contracts.py --output-dir /tmp/dlm-memory-contracts
```

The exporter writes review artifacts, not live publication records. All four
public tools get a fixed operation and closed wrapped input schema. Tool
annotations describe behavior, not authorization.

## Release work still required

Read `docs/dlm-lake-memory-engineering-handoff.md`. After the receiving-context,
selector and Core evidence contracts are implemented and tested, move the four
versioned Python files into the canonical adapter root, update the *incoming*
manifest/descriptor to 0.1.3 using supported runtime roles, preserve existing
reviewed helpers byte-for-byte, and run the official intake/package/coexistence
checks. Do not invent manifest providers, static tenant values or storage nodes
just to make intake validation pass. Existing Assets materialization owns old
version coexistence; do not copy historical manifests into a new submission.

No merge, promotion, deployment, live write, node provisioning or MCP publication
is authorized by this candidate. Unit tests prove consumer behavior only.

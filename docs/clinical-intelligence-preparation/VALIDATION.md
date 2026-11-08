# Preparation validation — updated 9 November 2026

## Local evidence

Environment: Windows, Python 3.13.5, `jsonschema==4.25.1` in the existing
developer virtual environment. No runtime package or dependency environment was
installed or upgraded by this preparation.

| Check | Result |
| --- | --- |
| `python -m unittest discover -s tests -p test_clinical_intelligence_preparation.py -v` | 51 passed |
| `python -m unittest discover -s tests -p test_adapter_intake_contract.py -v` | 2 passed |
| Draft 2020-12 schema validation | All 6 schemas valid; references resolved from the local registry only |
| Synthetic example validation | All 14 examples valid |
| CLI check of incomplete-subset review | Passed; authority/science/readiness explicitly unestablished |
| `git diff --check` | Passed |

The tests cover optional supplied identity, products/molecules/cases, two scope
modes, cross-class and molecule mismatch, explicit legacy crosswalk, incomplete
inventory, six independent completeness dimensions, denominator drift, retained
case joins, missing/partial provenance, comparability/critic prerequisites,
subset generalization rejection, safe run/status/readback shape, and forbidden
authority, raw-payload and mutation fields.

The review follow-up adds exact 128/129-item boundary cases, known oversized
counts hidden behind bounded prefixes, unknown extent/completeness, explicit
blocked overflow responses, producer-status normalization, unchanged scientific
flags, structural-versus-scientific issues, and deferred/unknown counters.

All persisted examples withhold class generalization. A constructed synthetic
test proves the structural eligible state is representable, then rejects each
missing prerequisite independently. Neither that test nor a schema-valid
`complete: true` establishes actual platform authority or scientific support.

## Review and side-effect boundary

Only preparation documentation, synthetic JSON, a pure offline checker, tests
and a dedicated read-only CI workflow are included. No files under `adapters/`
are changed. The new draft design has no `adapter.yaml`, manifest, launcher,
helper/support allowlist entry or catalog registration. The existing clinical
PR stack is untouched. No Assets materializer or promotion workflow is run.

No source or paid provider call, clinical assessment, DLM publication, Skill
write, database change, worker reconfiguration or deployment was performed.
Repository/Linear connector reads and authorized Linear progress updates are
distinct from clinical source/provider execution.

P1 was started with a source inspection and attempted read-only operator
inventory. The configured database read was unavailable after retrying with the
documented PHP 8.4 interpreter; no actual assessment or consumer authority was
verified. See [P1 status](P1_READ_PROOF.md). This is distinct from the offline
synthetic tests, which pass.

The dedicated GitHub workflow declares Python 3.10 and 3.13 on Ubuntu. Local
Windows validation does not establish that remote matrix; actual remote status
is reported on the draft PR and in the PI-2086 checklist when observed.
The initial `b960ae9` run passed 38+2 checks on both matrix versions. That is
historical evidence only; updated-head CI is tracked separately.

## Remaining qualification

The first governed retained assessment, authenticated ref mapping, actual
membership authority and eligibility policy, scientific methodology, neutral
assessment engine, durable public lifecycle, complete clinical orchestration
and exact deployed worker/source/Skill combination all remain unqualified.
Promotion remains excluded.

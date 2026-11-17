# Clinical Intelligence — adapter-intake preparation

Status: **draft contracts and synthetic validation only**. Prepared 8 November
2026 (Asia/Amman) from the supplied orchestration review and PI-2086.

This branch does not contain a runnable clinical gateway, an admitted clinical
reviewer, or a class-synthesis implementation. It creates no `adapter.yaml`,
asset manifest, launcher, runtime role, publication or promotion request.
**Do not promote this preparation to Assets.**

## Objective

Prepare one future ChatGPT-facing `nusaibah.clinical_intelligence_gateway`
behind the existing Assets Remote MCP facade, with separate internal product
review, neutral trial assessment, and pharmacological-class synthesis.

## System context

- [Source review](SOURCE_REVIEW.md) separates inspected implementation from
  proposed capabilities and records exact source revisions.
- [Contracts](CONTRACTS.md) defines identity, membership, assessment handoff,
  normalization and bounded result/status boundaries.
- [Delivery gates](DELIVERY_GATES.md) records dependencies, acceptance cases and
  the boundary before promotion.
- [Review refinements](REVIEW_REFINEMENTS.md) defines explicit overflow blocking
  and the producer-quality/structural-eligibility crosswalk.
- [P1 read proof](P1_READ_PROOF.md) records the attempted operator inventory,
  unavailable database read and exact remaining evidence; P1 has not passed.
- [Usage Skill contract](USAGE_SKILL_CONTRACT.md) separates future ChatGPT usage
  guidance from internal methodology, with exact proposed version, approved
  section reads and capability discovery. No Skill is installed or published.
- `schemas/` contains seven proposed JSON Schema Draft 2020-12 contracts: gateway
  request, class scope, retained handoff, coverage, class review, gateway response
  and guidance/usage contract.
- `examples/` contains wholly synthetic examples, with no patient or incident data.

The schema names end in `.draft.v1`. They are design artifacts, not admitted
runtime contracts or proof of platform authority. Schema validation cannot
establish scientific truth, provenance authenticity or deployment readiness.

## Approach and changes made

Freeze the public semantic request first. Separate server-owned retained input
from ChatGPT arguments. Make selected-subset coverage explicit. Preserve source
versions, reason graphs and partial/deferred quality. Class interpretation must
follow evidence normalization and an independent critic.

No existing failure assessment, source asset, fixed Skill, mutable Skill,
runtime catalog, Assets/Core/UI source or worker configuration is changed.
PI-1751 remains a dependency: this preparation does not implement its generic
assessment engine or its governed rulesets.

## Modularity impact

Core retains identity, node, object, provider and storage authority. Assets
retains admission, recorded runs, dispatch and result readback. Trusted runtime
hydrates approved inputs and invokes admitted roles. Business adapters remain
API-blind. Lake mode, S3, catalog and governance logic do not enter workflow
steps. No new scheduler, MCP server, persistence authority or graph store is
introduced.

## Validation

From the adapter-intake checkout, using a Python environment with `jsonschema`
4.x (validation was run with the exact environment recorded in VALIDATION.md):

```powershell
python -m unittest discover -s tests -p test_clinical_intelligence_preparation.py -v
python -m unittest discover -s tests -p test_clinical_gateway_guidance.py -v
python -m unittest discover -s tests -p test_adapter_intake_contract.py -v
python tools/check_clinical_preparation.py class-review docs/clinical-intelligence-preparation/examples/incomplete-subset.review.json
git diff --check
```

The dedicated preparation CI workflow runs only local contract tests. It has no
promotion job, provider access, publication step or deployment credentials.

## Risks / open questions

Class/group equivalence and the authoritative membership source remain open.
Both all-known-products and explicitly selected-subset requests are supported
in the draft; neither is a default claim of complete class evidence. Actual
retained and governed assessment availability, long-running public status,
exact clinical handler admission, scientific review quality and deployed
end-to-end execution remain unproven.

The next implementation slice is a read-only retained-assessment inspection
candidate after its exact input authority is demonstrated. Promotion remains
excluded from this branch and from the current user authorization.

Progress and explicit implementation questions are maintained as a checklist
on [PI-2086](https://linear.app/pipharma/issue/PI-2086). Both supplied planning
attachments have been incorporated. The exact modes are `all_known_in_snapshot`
and `selected_subset`; molecule/case selectors are supported as well as products.

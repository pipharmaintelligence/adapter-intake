# Verification - clinical consumer 0.1.1

## Exact source and local environment

The starting clinical source was obtained from the scoped GitHub Actions artifact
for commit dfa989db9e79ded01f046d91fc2fb8dd8871d19f on PR #143. This is a local
source snapshot, not a full network clone. Its configured origin is
pipharmaintelligence/adapter-intake. No other adapter is edited or validated here.

Python 3.13.5; jsonschema 4.26.0 locally. pi-obs-python-runtime is NOT installed in
this execution container. The package import test uses an explicit test-only
Adapter base stub; SDK-typed failure tests inject an explicit SDK exception double.
Neither is installed-wheel, live provider or signed-worker proof.

## Executed local gates

- Baseline: 162 provider-free tests passed before implementation.
- Revised consumer: 227 provider-free tests passed.
- Python 3.10 grammar and syntax/import checks.
- Existing legacy case/cohort fixtures plus prepared-evidence contract-only fixture.
- Exact optional binding ownership, source keys/versions/output roles and bundle hashes.
- NCT identity, protocol/results/arm separation, PMID metadata/abstract/history/integrity
  joins, date precision, candidate-only UMLS and source window omissions.
- Critic sibling/dependency containment, typed output exhaustion without retry,
  report/canonical-delta independence, default class-off and preview-only memory.
- Declared-file closure, exact prompt hashes and unchanged Fixed Skill digest.
- Local-root and isolated packaged imports with the stated test-only Adapter stub.

GitHub CI on the final pushed head must independently pass the existing intake
contract plus Linux/Windows Python 3.10/3.13 clinical lanes. The PR and Linear note
record that exact final head and observed CI state; this file is not a CI receipt.

## Not established

Actual source-adapter validation (parallel user work), real source records, live
binding preparation, installed SDK, official Assets materialization, model/provider
admission, scientific accuracy, actual product-memory initialization/apply,
retention/readback/history, ECS deployment and process-loss recovery. No live
clinical or commercial conclusion is certified by these synthetic fixtures.

# F3 — draft gateway Fixed Skill dependency

This isolated development contract declares the approved usage Skill in the actual
Assets descriptor structure. It is stacked on package draft #175, which is stacked
on design draft #174. Neither parent changes. No release is authorized.

## Descriptor and exact dependency

Source: `contracts/clinical_intelligence_gateway/clinical_intelligence_gateway.asset.json`.
The candidate gateway identity is `nusaibah.clinical_intelligence_gateway@0.1.0`;
this version is a development contract, not an admitted asset.
Its `versions.0.1.0.skills` list contains exactly:

```json
{
  "skill_ref": "nusaibah.clinical-intelligence-gateway-usage",
  "version": "1.0.0",
  "digest": "sha256:873f0860e01664ec0459b408f9614818f4409142d3239df740b65cae5c5d43cc"
}
```

The descriptor contains a draft version, direct object input and object result
role. It has no active default, execution substrate, callable grant or publication
surface. It lives outside `adapters/` and `plugins/`, with no `adapter.yaml`,
adapter implementation or catalog change. It is deliberately not a complete
deployable package. Assets' metadata normalizer accepts the version; launch and
resume resolution reject its draft state.

The approved Skill remains the single sealed source in `skill-packages/`, with
unchanged `SKILL.md`, proof and ZIP. Local verification copies those exact bytes
into a temporary `skills/clinical-intelligence-gateway-usage/` layout required by
the official dependency validator, then deletes only the temporary directory.
There is no committed second Skill copy or network fallback. The internal
`nusaibah.clinical-failure-methodology@1.1.0` is not substituted or modified.

## Validation boundary

`tools/check_clinical_gateway_dependency.py` combines the existing F1/F2 exact-byte
proof with a narrow approval guard for this gateway descriptor. Wrong Skill
versions, namespace, digest, missing/duplicate/additional Skills, resolution-lane
substitution and lifecycle activation all fail. The generic portable validator
checks valid dependency syntax and package bytes; it accepts another valid SemVer
with identical bytes. The gateway-specific guard provides approval pinning.
It does not change the platform's runtime admission rules.

Official local verification uses current Assets source at
`ec70070eb3cd1111f00c8cb7e855a95e9d60e219`; the local checkout's relevant files
match that source. It verifies pinned SHA-256 hashes before invoking:

- `devtools.skill_package.validate_manifest_skill_dependencies` on the actual
  `versions.0.1.0` object and unchanged temporary package;
- `AssetManifestRegistry` and `AssetIdentityResolver::skillDependencies` on the
  actual descriptor, followed by launch/resume rejection checks.

The PHP helper loads Composer autoload only. It injects descriptor metadata and
an unused catalog path; it does not bootstrap Laravel, read `.env`, connect to a
database, publish a catalog or start a worker. A PHP version compatible with
Assets' Composer dependencies is required (PHP 8.4 used locally).

Run in this checkout (use local paths for the two explicit dependencies):

```text
python tools/check_clinical_gateway_dependency.py --integrity-only
python -m unittest discover -s tests -p test_clinical_gateway_dependency.py -v
python -m unittest discover -s tests -p test_adapter_intake_contract.py -v

python tools/check_clinical_gateway_dependency.py --runtime-source <Assets-checkout> --php-binary <compatible-php> --write-proof
```

For the four official positive/negative tests, set
`CLINICAL_USAGE_RUNTIME_SOURCE=<Assets-checkout>` and
`CLINICAL_GATEWAY_PHP_BINARY=<compatible-php>`, then run:

```text
python -m unittest discover -s tests -p test_clinical_gateway_dependency_assets.py -v
```

`local-validation.json` records the executed official local result, descriptor
hash and validator source hashes. The public Windows/Linux × Python 3.10/3.13 CI
runs the ten public approval tests, exact-byte reproduction and two existing intake
checks. It explicitly reports both official-validator execution flags as false;
it cannot rerun private Assets validators and does not treat the saved local proof
as a fresh CI result.

Local result: **10 public contract tests + 4 official Assets tests + 2 existing
intake checks passed** on Windows Python 3.13.16. PHP syntax validation and Git
diff checks also passed. The descriptor normalized with one exact Skill; both
launch and resume were rejected. Package source, proof and ZIP have no diff
against parent #175 at `d3e3fd7507bd9e7c1442429a09ecec93016dde55`.

## Remaining gates

F3 establishes a local manifest dependency contract only. Assembly into an actual
gateway source package, runtime admission/hydration, signed worker transport,
MCP publication, ChatGPT installation and live guidance consumption remain
unverified and unauthorized here. The P1 retained clinical assessment readback
is still a separate blocker for scientific execution. No provider work, retained
assessment read, DLM/DB/Skill mutation, merge, promotion or deployment is performed.

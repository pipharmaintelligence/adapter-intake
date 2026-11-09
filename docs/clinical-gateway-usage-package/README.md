# Clinical Gateway Fixed usage package — F1/F2 proof

Status: **package valid and exact bytes verified; release not authorized**.
Prepared 9 November 2026 in an isolated development branch stacked on draft
PR #174 at `1de3239621031d46656aafffe67d3e91f152e7c1`. PR #174 itself is unchanged
and remains design-only. This slice adds no gateway adapter or runtime binding.

## Approved identity and artifact

`nusaibah.clinical-intelligence-gateway-usage@1.0.0`

Canonical portable package digest:

```text
sha256:873f0860e01664ec0459b408f9614818f4409142d3239df740b65cae5c5d43cc
```

| Exact artifact | Size / SHA-256 |
| --- | --- |
| Canonical package | 1 file, 4,122 bytes, UTF-8 with LF |
| `SKILL.md` document bytes | `d99e0faa95f148c9f1f677489f775b8787fdfed7ccfa99edfb55f18d22765c3e` |
| Deterministic flat ZIP | 4,236 bytes; `c19aaf710ebd6f8b7ec1f291a5614823b927ae279919d814673456119c95c648` |

The canonical digest is **not** the document or ZIP checksum. The Assets
portable validator hashes the canonical sorted list of relative file paths
and each file's exact SHA-256. ZIP metadata uses a fixed timestamp, fixed file
permissions and stored bytes; extraction reproduces the canonical identity.

The package, ZIP and machine-readable `package-proof.json` are under
`skill-packages/nusaibah/clinical-intelligence-gateway-usage/1.0.0/`. The proof is
outside the package root, so adding validation evidence cannot change the
canonical package or create a circular checksum. Git attributes preserve the
exact package and archive bytes across checkout platforms.

## Approval and instruction preservation

The approved seven sections come from the immutable PR #174 approval snapshot:

- repository `pipharmaintelligence/adapter-intake`;
- commit `1de3239621031d46656aafffe67d3e91f152e7c1`;
- `docs/clinical-intelligence-preparation/gateway-usage.contract.json`;
- Git blob `f61a119c6e908683747f72e1cfb2163324b78343`;
- user approval recorded in PI-2086 comment `36574fb4-c366-443d-b5d7-1df8c1797ae0`.

The package preserves every approved section body verbatim as UTF-8, in the
approved order. It adds only the portable name/description frontmatter, title
and section headings. Version is carried by the exact external package
reference and version directory; unsupported `version` frontmatter is not added.

`SKILL.md` is the finalized instruction source for later packaging/consumption.
Python contains no duplicate instruction bodies. The frozen design JSON is an
approval reference, not a second mutable runtime instruction source. A future
host package or MCP section projection must use this exact approved package,
not independently rewritten copies. Existing internal clinical methodology
`nusaibah.clinical-failure-methodology@1.1.0` remains untouched.

## F1 — current portable validator PASS

Validation used the current Assets `devtools.skill_package` implementation:

- repository `piusaibah/assets`, main observed at
  `ec70070eb3cd1111f00c8cb7e855a95e9d60e219`;
- module `python_runtime/devtools/skill_package.py`;
- Git blob `38b97bd0602013378b775b3f344cd24992a02414`;
- source-file SHA-256
  `55642ead57017fc2469e2a3d9542842d8cadf4c58b174fbbb71b1a0b369ed1e9`.

The tooling checks that exact validator source before importing it. It calls
`validate_skill_package`, `compute_skill_package_digest` and the exact-reference
parser. The independent canonical-manifest calculation agrees with the current
validator; ZIP extraction validates to the same digest and byte count.

The portable limits are 64 files, 1,048,576 bytes per file and 4,194,304 total
bytes. The package passes identity, frontmatter, directory/layout and UTF-8
checks. Ten offline package tests cover the exact valid artifact and approval,
digest sensitivity, wrong identity, unsupported frontmatter, invalid UTF-8,
hidden/executable layout and each file/count/total boundary plus excess.
The two existing adapter-intake checks pass separately. Codex skill-creator's
`quick_validate.py` also passes; it is a supplementary frontmatter check, not a
replacement for the portable validator. Local Python was 3.13.16 on Windows.

## F2 — exact-byte proof PASS

The committed proof records per-file and per-section hashes, exact approval
source, canonical identity, validator provenance, archive size/checksum and
round-trip identity. The verifier checks these without rewriting the package.
Changing an instruction byte, newline, recorded digest or release flag is
detected. No digest is inferred from a tool name, version label or text alone.

Run full official validation in a checkout with read access to the pinned
Assets source:

```powershell
$env:CLINICAL_USAGE_RUNTIME_SOURCE = 'C:\xampp\htdocs\assets'
python tools/package_clinical_gateway_usage_skill.py --runtime-source $env:CLINICAL_USAGE_RUNTIME_SOURCE
python -m unittest discover -s tests -p test_clinical_gateway_usage_package.py -v
python -m unittest discover -s tests -p test_adapter_intake_contract.py -v
```

Use `--write-proof` only to reproduce the local ZIP and proof after validating
finalized source. It never rewrites `SKILL.md`, installs a Skill or publishes
anything. Subsequent runs without that flag verify the committed exact bytes.

## Public CI scope

Assets is private; this public intake CI must not assume cross-repository
credentials or copy private validator source. The dedicated Ubuntu/Windows,
Python 3.10/3.13 matrix therefore runs:

```text
python tools/package_clinical_gateway_usage_skill.py --integrity-only
python -m unittest discover -s tests -p test_adapter_intake_contract.py -v
```

This reconstructs the approved document, per-file/canonical hashes and exact
ZIP bytes using public source only. Its report explicitly states
`portable_validator_executed=false`: it verifies F2 and the recorded F1 source
identity, not a fresh private-validator run. The official portable validation
and boundary tests above were executed locally against the verified current
source. The matrix's actual status is recorded on the new draft and PI-2086;
source declarations alone are not CI evidence.

## Authorization boundary

This is a standalone source package and reproducible proof, not an admitted
asset or installed host Skill. No `adapter.yaml`, gateway manifest, Skill
publication row, mutable role, registry update or runtime setting is added.
The proof records publication, installation, runtime admission, gateway
consumption, P1 qualification and release authorization as false.

No merge, Assets promotion, deployment, provider/source execution, DLM write,
Skill publication, ChatGPT installation or live consumption occurred. P1
retained-assessment readback remains a separate outstanding gate. Future gateway
source must bind the exact approved ref/version/digest only after its own
authoring and authorization; package validity does not grant that authority.

"""F3 offline draft descriptor proof. No catalog, runtime or release writes."""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import tempfile
from pathlib import Path

import package_clinical_gateway_usage_skill as package

ROOT = Path(__file__).resolve().parents[1]
DESCRIPTOR = ROOT / "contracts/clinical_intelligence_gateway/clinical_intelligence_gateway.asset.json"
PROOF = ROOT / "docs/clinical-gateway-dependency/local-validation.json"
ASSET_KEY = "nusaibah.clinical_intelligence_gateway"
ASSET_VERSION = "0.1.0"
IDENTITY = {
    "skill_ref": "nusaibah.clinical-intelligence-gateway-usage",
    "version": "1.0.0",
    "digest": "sha256:873f0860e01664ec0459b408f9614818f4409142d3239df740b65cae5c5d43cc",
}
PHP_SOURCES = {
    "app/Observability/InnovationLab/Services/AssetIdentityResolver.php":
        "9e4f83a946531576cc60a53b3209041bfc4d6a167ed400842413e845f49c78d8",
    "app/Observability/InnovationLab/Services/AssetManifestRegistry.php":
        "83fd62092858058798f4ac8dae5dc76fed2ed66c0bb74bbfe058b7833bb691d3",
}


class DependencyContractError(ValueError):
    pass


def require(condition: bool, code: str) -> None:
    if not condition:
        raise DependencyContractError(code)


def validate_descriptor(value: object) -> dict:
    """Freeze this development slice; generic validators do not pin approval."""
    require(isinstance(value, dict) and set(value) == {"key", "versions"}, "draft_descriptor_fields_changed")
    require(value["key"] == ASSET_KEY, "gateway_identity_changed")
    versions = value["versions"]
    require(isinstance(versions, dict) and set(versions) == {ASSET_VERSION}, "gateway_version_changed")
    version = versions[ASSET_VERSION]
    require(isinstance(version, dict) and set(version) == {
        "state", "allow_resume", "inputs", "outputs", "skills"}, "draft_version_fields_changed")
    require(version["state"] == "draft" and version["allow_resume"] is False, "gateway_must_remain_draft")
    require(version["inputs"] == {"variables": {"required": True, "source": "direct", "shape": "object"}}
            and version["outputs"] == {"result": {"required": True, "shape": "object"}},
            "gateway_io_contract_changed")
    require(version["skills"] == [IDENTITY], "approved_skill_dependency_required")
    return version


def verify_public_contract() -> dict:
    integrity = package.verify_recorded_integrity()
    require(integrity["identity"] == IDENTITY, "sealed_package_identity_changed")
    validate_descriptor(json.loads(DESCRIPTOR.read_text(encoding="utf-8")))
    return {
        "status": "f3_contract_verified",
        "asset_key": ASSET_KEY,
        "asset_version": ASSET_VERSION,
        "identity": IDENTITY,
        "descriptor_sha256": hashlib.sha256(DESCRIPTOR.read_bytes()).hexdigest(),
        "portable_validator_executed": False,
        "assets_descriptor_normalizer_executed": False,
        "runtime_admitted": False,
        "gateway_consumed": False,
        "release_authorized": False,
    }


def stage_package(root: Path, descriptor: dict) -> Path:
    """Temporary expected asset layout; never duplicate the committed Skill."""
    target = root / DESCRIPTOR.name
    target.write_text(json.dumps(descriptor), encoding="utf-8")
    shutil.copytree(package.PACKAGE_ROOT, root / "skills" / package.NAME)
    return target


def verify_official_contract(runtime_source: Path, php_binary: Path) -> dict:
    result = verify_public_contract()
    source = runtime_source.resolve()
    validator = package.load_validator(source)
    for path, digest in PHP_SOURCES.items():
        require(hashlib.sha256((source / path).read_bytes()).hexdigest() == digest,
                "assets_descriptor_validator_source_changed")
    descriptor = json.loads(DESCRIPTOR.read_text(encoding="utf-8"))
    version = validate_descriptor(descriptor)
    with tempfile.TemporaryDirectory(prefix="clinical-gateway-f3-") as directory:
        root = Path(directory)
        manifest = stage_package(root, descriptor)
        report = validator.validate_manifest_skill_dependencies(asset_root=root, version_manifest=version)
        require(report["status"] == "ready" and report["validated_count"] == 1
                and report["blocked_count"] == 0, "official_skill_dependency_validation_failed")
        completed = subprocess.run([
            str(php_binary), str(ROOT / "tools/check_clinical_gateway_descriptor.php"),
            str(source), str(manifest), ASSET_KEY, ASSET_VERSION,
        ], capture_output=True, text=True, check=True)
        normalization = json.loads(completed.stdout)
        require(normalization["skills"] == [IDENTITY] and normalization["launch_rejected"] is True
                and normalization["resume_rejected"] is True, "official_descriptor_validation_failed")
    result.update({
        "portable_validator_executed": True,
        "assets_descriptor_normalizer_executed": True,
        "assets_source_commit": package.VALIDATOR_COMMIT,
        "verified_source_sha256": {**PHP_SOURCES, "python_runtime/devtools/skill_package.py": package.VALIDATOR_SHA256},
        "skill_dependency_report": report,
        "descriptor_normalization": normalization,
    })
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--integrity-only", action="store_true")
    mode.add_argument("--runtime-source", type=Path)
    parser.add_argument("--php-binary", type=Path)
    parser.add_argument("--write-proof", action="store_true")
    args = parser.parse_args()
    if args.integrity_only:
        if args.write_proof or args.php_binary:
            parser.error("integrity-only does not execute official validators or write their evidence")
        result = verify_public_contract()
    else:
        if not args.php_binary:
            parser.error("--runtime-source requires --php-binary (PHP compatible with Assets dependencies)")
        result = verify_official_contract(args.runtime_source, args.php_binary)
        if args.write_proof:
            PROOF.write_bytes((json.dumps(result, indent=2) + "\n").encode("utf-8"))
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()

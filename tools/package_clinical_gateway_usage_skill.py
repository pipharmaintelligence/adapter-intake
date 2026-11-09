"""Offline Fixed Skill package proof; never publish, install or admit a Skill."""
from __future__ import annotations

import argparse
import hashlib
import importlib
import io
import json
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
NAME = "clinical-intelligence-gateway-usage"
SKILL_REF = "nusaibah." + NAME
VERSION = "1.0.0"
APPROVED_COMMIT = "1de3239621031d46656aafffe67d3e91f152e7c1"
APPROVED_PATH = "docs/clinical-intelligence-preparation/gateway-usage.contract.json"
VALIDATOR_COMMIT = "ec70070eb3cd1111f00c8cb7e855a95e9d60e219"
VALIDATOR_BLOB = "38b97bd0602013378b775b3f344cd24992a02414"
VALIDATOR_SHA256 = "55642ead57017fc2469e2a3d9542842d8cadf4c58b174fbbb71b1a0b369ed1e9"
VERSION_ROOT = ROOT / "skill-packages" / "nusaibah" / NAME / VERSION
PACKAGE_ROOT = VERSION_ROOT / NAME
ARCHIVE = VERSION_ROOT / (NAME + "-" + VERSION + ".zip")
PROOF = VERSION_ROOT / "package-proof.json"
SECTIONS = ("overview", "existing_review", "neutral_assessment", "class_review", "get_status", "get_result", "result_states")
DESCRIPTION = "Select Clinical Intelligence Gateway operations and interpret blocked, partial and retained results. Use for clinical review requests and follow-ups; scientific analysis remains in separately governed specialist Skills."


class PackageProofError(ValueError):
    pass


def require(ok: bool, code: str) -> None:
    if not ok:
        raise PackageProofError(code)


def git(*args: str) -> bytes:
    return subprocess.run(["git", "-c", "safe.directory=" + ROOT.as_posix(), "-C", str(ROOT), *args],
                          capture_output=True, check=True).stdout


def approved_contract() -> tuple[dict, str]:
    raw = git("show", APPROVED_COMMIT + ":" + APPROVED_PATH)
    contract = json.loads(raw)
    require(contract["proposed_skill"]["skill_ref"] == SKILL_REF
            and contract["proposed_skill"]["version"] == VERSION, "approved_identity_changed")
    require(tuple(row["section_id"] for row in contract["sections"]) == SECTIONS, "approved_sections_changed")
    return contract, git("rev-parse", APPROVED_COMMIT + ":" + APPROVED_PATH).decode("ascii").strip()


def approved_markdown() -> bytes:
    """Approval snapshot is a historical constraint, not runtime instructions."""
    contract, _ = approved_contract()
    prefix = "---\nname: " + NAME + "\ndescription: " + DESCRIPTION + "\n---\n\n# Clinical Intelligence Gateway Usage\n\n"
    body = "\n\n".join("## " + row["section_id"] + "\n\n" + row["instructions"] for row in contract["sections"])
    return (prefix + body + "\n").encode("utf-8")


def load_validator(runtime_source: Path):
    source = runtime_source.resolve()
    module_path = source / "python_runtime/devtools/skill_package.py"
    require(hashlib.sha256(module_path.read_bytes()).hexdigest() == VALIDATOR_SHA256, "portable_validator_source_changed")
    sys.path.insert(0, str(source / "python_runtime"))
    validator = importlib.import_module("devtools.skill_package")
    require(Path(validator.__file__).resolve() == module_path, "unexpected_portable_validator_loaded")
    return validator


def deterministic_archive(package_root: Path) -> bytes:
    """Flat portable ZIP with fixed metadata and stored exact file bytes."""
    target = io.BytesIO()
    with zipfile.ZipFile(target, "w", compression=zipfile.ZIP_STORED) as archive:
        for path in sorted(package_root.rglob("*")):
            if not path.is_file():
                continue
            info = zipfile.ZipInfo(path.relative_to(package_root).as_posix(), date_time=(1980, 1, 1, 0, 0, 0))
            info.create_system = 3
            info.external_attr = 0o100644 << 16
            info.compress_type = zipfile.ZIP_STORED
            archive.writestr(info, path.read_bytes())
    return target.getvalue()


def canonical_digest(files: list[dict]) -> str:
    entries = [{"path": row["path"], "sha256": row["sha256"]} for row in files]
    canonical = json.dumps(sorted(entries, key=lambda row: row["path"]), ensure_ascii=False,
                           sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
    return "sha256:" + hashlib.sha256(canonical).hexdigest()


def inspect_package(validator) -> tuple[dict, bytes]:
    package = validator.validate_skill_package(PACKAGE_ROOT, expected_name=NAME)
    require((PACKAGE_ROOT / "SKILL.md").read_bytes() == approved_markdown(), "approved_instruction_bytes_changed")
    require(package.file_count == 1, "unexpected_package_resource")
    files = [{"path": path.relative_to(PACKAGE_ROOT).as_posix(), "size_bytes": len(path.read_bytes()),
              "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
             for path in sorted(PACKAGE_ROOT.rglob("*")) if path.is_file()]
    require(canonical_digest(files) == package.digest == validator.compute_skill_package_digest(PACKAGE_ROOT),
            "canonical_digest_disagreement")
    reference = {"skill_ref": SKILL_REF, "version": VERSION, "digest": package.digest}
    parsed = validator.skill_references_for_version({"skills": [reference]})
    require(len(parsed) == 1 and parsed[0].name == NAME, "portable_reference_invalid")
    archive = deterministic_archive(PACKAGE_ROOT)
    # Round-trip only an archive constructed from already validated package paths.
    with tempfile.TemporaryDirectory() as temp:
        extracted = Path(temp) / NAME
        with zipfile.ZipFile(io.BytesIO(archive)) as reader:
            reader.extractall(extracted)
        round_trip = validator.validate_skill_package(extracted, expected_name=NAME)
        require(round_trip.digest == package.digest and round_trip.total_bytes == package.total_bytes,
                "archive_roundtrip_changed_package")
    contract, approved_blob = approved_contract()
    proof = {
        "schema_version": "clinical_gateway_usage_package_proof.v1", "status": "package_valid_exact_bytes_verified",
        "identity": reference,
        "approval": {"repository": "pipharmaintelligence/adapter-intake", "commit": APPROVED_COMMIT,
                     "path": APPROVED_PATH, "git_blob_sha": approved_blob,
                     "sections": [{"section_id": row["section_id"], "utf8_bytes": len(row["instructions"].encode("utf-8")),
                                   "sha256": hashlib.sha256(row["instructions"].encode("utf-8")).hexdigest()}
                                  for row in contract["sections"]]},
        "package": {"path": PACKAGE_ROOT.relative_to(ROOT).as_posix(), "file_count": package.file_count,
                    "total_bytes": package.total_bytes, "encoding": "utf-8", "line_endings": "LF",
                    "files": files, "approved_instructions_preserved": True},
        "validator": {"repository": "piusaibah/assets", "commit": VALIDATOR_COMMIT,
                      "path": "python_runtime/devtools/skill_package.py", "git_blob_sha": VALIDATOR_BLOB,
                      "sha256": VALIDATOR_SHA256, "entrypoint": "validate_skill_package",
                      "limits": {"max_files": validator.MAX_SKILL_FILES, "max_file_bytes": validator.MAX_SKILL_FILE_BYTES,
                                 "max_package_bytes": validator.MAX_SKILL_PACKAGE_BYTES}},
        "archive": {"path": ARCHIVE.relative_to(ROOT).as_posix(), "format": "ZIP_STORED",
                    "size_bytes": len(archive), "sha256": hashlib.sha256(archive).hexdigest(),
                    "roundtrip_canonical_digest": round_trip.digest},
        "release_authorized": False, "published": False, "runtime_admitted": False, "installed": False,
        "gateway_consumed": False, "p1_qualified": False,
    }
    return proof, archive


def verify_recorded_integrity() -> dict:
    """Recheck exact public bytes; does not rerun the private Assets validator."""
    proof = json.loads(PROOF.read_text(encoding="utf-8"))
    require((PACKAGE_ROOT / "SKILL.md").read_bytes() == approved_markdown(), "approved_instruction_bytes_changed")
    files = [{"path": path.relative_to(PACKAGE_ROOT).as_posix(), "size_bytes": len(path.read_bytes()),
              "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
             for path in sorted(PACKAGE_ROOT.rglob("*")) if path.is_file()]
    require([row["path"] for row in files] == ["SKILL.md"], "unexpected_package_resource")
    require(proof["identity"] == {"skill_ref": SKILL_REF, "version": VERSION, "digest": canonical_digest(files)},
            "recorded_canonical_identity_changed")
    require(proof["package"] == {"path": PACKAGE_ROOT.relative_to(ROOT).as_posix(), "file_count": len(files),
            "total_bytes": sum(row["size_bytes"] for row in files), "encoding": "utf-8", "line_endings": "LF",
            "files": files, "approved_instructions_preserved": True}, "recorded_package_bytes_changed")
    contract, source_blob = approved_contract()
    require(proof["approval"] == {"repository": "pipharmaintelligence/adapter-intake", "commit": APPROVED_COMMIT,
            "path": APPROVED_PATH, "git_blob_sha": source_blob,
            "sections": [{"section_id": row["section_id"], "utf8_bytes": len(row["instructions"].encode("utf-8")),
                          "sha256": hashlib.sha256(row["instructions"].encode("utf-8")).hexdigest()}
                         for row in contract["sections"]]}, "approval_snapshot_changed")
    require(proof["validator"]["commit"] == VALIDATOR_COMMIT and proof["validator"]["git_blob_sha"] == VALIDATOR_BLOB
            and proof["validator"]["sha256"] == VALIDATOR_SHA256, "recorded_validator_identity_changed")
    archive = deterministic_archive(PACKAGE_ROOT)
    require(ARCHIVE.read_bytes() == archive and proof["archive"] == {
        "path": ARCHIVE.relative_to(ROOT).as_posix(), "format": "ZIP_STORED", "size_bytes": len(archive),
        "sha256": hashlib.sha256(archive).hexdigest(), "roundtrip_canonical_digest": proof["identity"]["digest"]},
        "recorded_archive_bytes_changed")
    for flag in ("release_authorized", "published", "runtime_admitted", "installed", "gateway_consumed", "p1_qualified"):
        require(proof[flag] is False, "unauthorized_release_claim")
    return {"status": "exact_bytes_verified", "identity": proof["identity"], "portable_validator_executed": False,
            "zip_sha256": proof["archive"]["sha256"], "release_authorized": False}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--runtime-source", type=Path, help="Checkout of the pinned current Assets validator source")
    mode.add_argument("--integrity-only", action="store_true", help="Verify recorded public bytes without private validator access")
    parser.add_argument("--write-proof", action="store_true", help="Write only local ZIP and proof, never Skill content or a release")
    args = parser.parse_args()
    if args.integrity_only:
        if args.write_proof:
            parser.error("--write-proof requires --runtime-source; byte verification cannot create validation evidence")
        print(json.dumps(verify_recorded_integrity(), indent=2))
        return
    validator = load_validator(args.runtime_source)
    proof, archive = inspect_package(validator)
    encoded = (json.dumps(proof, indent=2, ensure_ascii=False) + "\n").encode("utf-8")
    if args.write_proof:
        ARCHIVE.write_bytes(archive)
        PROOF.write_bytes(encoded)
    else:
        require(PROOF.read_bytes() == encoded, "recorded_package_proof_changed")
        require(ARCHIVE.read_bytes() == archive, "recorded_archive_bytes_changed")
    print(json.dumps({"status": proof["status"], "identity": proof["identity"],
                      "file_count": proof["package"]["file_count"], "total_bytes": proof["package"]["total_bytes"],
                      "zip_sha256": proof["archive"]["sha256"], "release_authorized": False}, indent=2))


if __name__ == "__main__":
    main()

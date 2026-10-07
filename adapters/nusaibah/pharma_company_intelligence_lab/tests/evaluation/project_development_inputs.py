"""Offline, truth-free development input export. Never launches a runtime run."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import tempfile
from typing import Any

import supplied_source_candidate_evaluation as candidate

HERE = Path(__file__).resolve().parent
BINDINGS_PATH = HERE / "development_input_bindings.v1.json"
MAX_CASES = 16
MAX_FILE_BYTES = 2 * 1024 * 1024
TOKEN = re.compile(r"^[a-z][a-z0-9_.-]{0,95}$")
SHA256 = re.compile(r"^[0-9a-f]{64}$")


class ProjectionError(ValueError):
    """Only static reason codes reach the CLI; source/exception text stays local."""


def encode(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, sort_keys=True,
                       separators=(",", ":"), allow_nan=False) + "\n").encode("utf-8")


def sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _require(condition: bool, reason: str) -> None:
    if not condition:
        raise ProjectionError(reason)


def _object_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    value: dict[str, Any] = {}
    for key, item in pairs:
        _require(key not in value, "duplicate_json_key")
        value[key] = item
    return value


def _reject_constant(_: str) -> None:
    raise ProjectionError("nonfinite_json_value")


def load_snapshot(path: Path) -> tuple[dict[str, Any], str]:
    # Hash and parse the same bounded bytes, including any UTF-8 BOM/newlines.
    with path.open("rb") as handle:
        payload = handle.read(MAX_FILE_BYTES + 1)
    _require(len(payload) <= MAX_FILE_BYTES, "input_file_size_exceeded")
    value = json.loads(payload.decode("utf-8-sig"), object_pairs_hook=_object_pairs,
                       parse_constant=_reject_constant)
    _require(isinstance(value, dict), "json_object_required")
    return value, sha256(payload)


def _binding_index(suite: dict[str, Any], bindings: dict[str, Any],
                   suite_sha256: str, candidate_version: str) -> dict[str, dict[str, Any]]:
    _require(set(bindings) == {"schema_version", "decision_status", "suite_id",
                              "suite_byte_sha256", "candidate_identity", "bindings"},
             "binding_fields_invalid")
    _require(bindings["schema_version"] == "pharma_development_input_bindings.v1"
             and bindings["decision_status"] == "proposed", "binding_contract_invalid")
    _require(suite.get("schema_version") == "pharma_review_evaluation_suite.v1"
             and isinstance(suite.get("suite_id"), str)
             and TOKEN.fullmatch(suite["suite_id"]) is not None
             and bindings["suite_id"] == suite["suite_id"], "suite_identity_invalid")
    pinned_hashes = bindings["suite_byte_sha256"]
    _require(isinstance(pinned_hashes, list) and 1 <= len(pinned_hashes) <= 2
             and all(isinstance(value, str) and SHA256.fullmatch(value) for value in pinned_hashes)
             and len(set(pinned_hashes)) == len(pinned_hashes), "suite_digest_pins_invalid")
    _require(isinstance(suite_sha256, str) and suite_sha256 in pinned_hashes,
             "suite_digest_mismatch")
    _require(candidate_version in candidate.CANDIDATE_VERSIONS
             and bindings["candidate_identity"] == f"{candidate.CANDIDATE_ASSET_KEY}:{candidate_version}",
             "candidate_identity_mismatch")
    raw = bindings["bindings"]
    _require(isinstance(raw, list) and 1 <= len(raw) <= MAX_CASES, "binding_count_invalid")
    index: dict[str, dict[str, Any]] = {}
    for binding in raw:
        _require(isinstance(binding, dict) and set(binding) == {
            "case_id", "entity_id", "entity_name", "source_sha256"}, "binding_fields_invalid")
        for field in ("case_id", "entity_id"):
            _require(isinstance(binding[field], str)
                     and TOKEN.fullmatch(binding[field]) is not None, "binding_identity_invalid")
        _require(binding["case_id"] not in index, "duplicate_binding")
        _require(isinstance(binding["entity_name"], str)
                 and 1 <= len(binding["entity_name"].strip()) <= 160, "binding_name_invalid")
        _require(isinstance(binding["source_sha256"], str)
                 and SHA256.fullmatch(binding["source_sha256"]) is not None,
                 "binding_source_digest_invalid")
        index[binding["case_id"]] = binding
    return index


def project_batch(suite: dict[str, Any], bindings: dict[str, Any], case_ids: list[str], *,
                  suite_sha256: str, binding_sha256: str,
                  candidate_version: str = candidate.CANDIDATE_ASSET_VERSION) -> tuple[dict[str, Any], dict[str, bytes]]:
    """Return a text-free manifest and exact inputs; held-out truth is never consulted."""
    _require(isinstance(case_ids, list) and 1 <= len(case_ids) <= MAX_CASES,
             "case_count_invalid")
    _require(all(isinstance(value, str) and TOKEN.fullmatch(value) for value in case_ids),
             "case_identity_invalid")
    _require(len(set(case_ids)) == len(case_ids), "duplicate_case")
    _require(isinstance(binding_sha256, str) and SHA256.fullmatch(binding_sha256) is not None,
             "binding_digest_invalid")
    index = _binding_index(suite, bindings, suite_sha256, candidate_version)
    _require(isinstance(suite.get("cases"), list), "suite_cases_invalid")
    receipts = []
    outputs: dict[str, bytes] = {}
    for case_id in case_ids:
        matches = [case for case in suite["cases"]
                   if isinstance(case, dict) and case.get("case_id") == case_id]
        _require(len(matches) == 1, "fixture_identity_invalid")
        # Reject before reading source, adjudication or any expected-answer fields.
        _require(matches[0].get("split") == "development", "development_only")
        _require(case_id in index, "case_binding_missing")
        try:
            case = candidate.find_fixture(suite, case_id)
        except (candidate.CandidateEvaluationError, TypeError, ValueError, AttributeError):
            raise ProjectionError("fixture_validation_rejected") from None
        binding = index[case_id]
        _require(case["source_identity"].get("source_id") == f"synthetic:{case_id}"
                 and case["source_identity"].get("source_version") == "synthetic.v1",
                 "synthetic_source_identity_required")
        _require(case["source_identity"]["content_sha256"] == binding["source_sha256"],
                 "binding_source_digest_mismatch")
        compatibility = candidate.assess_fixture_compatibility(case)
        receipt: dict[str, Any] = {"case_id": case_id, "source_sha256": binding["source_sha256"],
                                   "reason_codes": compatibility["reason_codes"]}
        if compatibility["status"] == "not_executable":
            receipts.append({**receipt, "projection_status": "not_executable"})
            continue
        units = []
        for unit in case["source_units"]:
            flags = unit.get("quality_flags", [])
            _require(isinstance(flags, list) and all(isinstance(flag, str) for flag in flags),
                     "source_flags_invalid")
            wrong_entity = bool(set(flags) & candidate.WRONG_ENTITY_FLAGS)
            # Distractor IDs identify exclusions only; never infer an actual company name.
            entity_id = ("excluded-" + sha256(unit["locator"].encode("utf-8"))[:24]
                         if wrong_entity else binding["entity_id"])
            _require(not wrong_entity or entity_id != binding["entity_id"],
                     "distractor_identity_collision")
            units.append({"locator": unit["locator"], "entity_id": entity_id,
                          "text": unit["text"],
                          "accessible": not bool(set(flags) & candidate.INACCESSIBLE_FLAGS),
                          "related_locators": list(unit.get("related_locators", []))})
        inputs = {"variables": {"execution_purpose": "supplied_source_review"},
                  "evaluation_case": {"records": [{"case_id": case_id,
                      "mode": "supplied_source_review", "synthetic": True,
                      "entity_id": binding["entity_id"], "entity_name": binding["entity_name"],
                      "source_units": units}]}}
        try:
            # Reuse PR80's unchanged validator, including prepare_review's context bounds.
            context = candidate.validate_inputs_against_fixture(case, inputs, candidate_version=candidate_version)
        except candidate.CandidateEvaluationError:
            receipts.append({**receipt, "projection_status": "not_executable",
                             "reason_codes": ["candidate_input_preflight_rejected"]})
            continue
        prepared = context["prepared_review"]
        payload = encode(inputs)
        filename = f"{case_id}.inputs.json"
        outputs[filename] = payload
        receipts.append({**receipt, "projection_status": "ready", "inputs_file": filename,
                         "inputs_sha256": sha256(payload), "inputs_size_bytes": len(payload),
                         "source_unit_count": len(units), "chunk_count": len(prepared["chunks"]),
                         "excluded_entity_count": sum(unit["disposition"] == "excluded_by_entity"
                                                      for unit in prepared["inventory"]),
                         "inaccessible_count": sum(unit["disposition"] == "inaccessible"
                                                   for unit in prepared["inventory"]),
                         "snapshot_id": prepared["snapshot_id"], "plan": prepared["plan"]})
    ready = len(outputs) == len(case_ids)
    report = {"schema_version": "pharma_development_input_projection.v1",
              "status": "prepared" if ready else "blocked",
              "suite_id": suite["suite_id"], "suite_sha256": suite_sha256,
              "bindings_sha256": binding_sha256,
              "candidate_identity": f"{candidate.CANDIDATE_ASSET_KEY}:{candidate_version}",
              "expected_case_ids": list(case_ids), "declared_case_count": len(case_ids),
              "ready_case_count": len(outputs), "cases": receipts,
              "execution_allowed": False, "scope_decision_status": "proposed",
              "baseline_comparable": False, "wp1_complete": False, "wp2_unblocked": False,
              "provider_invocations": 0, "values_included": False,
              "inputs_exported": False,
              "next_action": "obtain scope and runtime admission review before execution"}
    # A finite batch is all-or-nothing. Negative classifications never silently shrink it.
    return report, outputs if ready else {}


def export_batch(output_dir: Path, report: dict[str, Any], outputs: dict[str, bytes]) -> None:
    _require(report["status"] == "prepared" and bool(outputs), "batch_not_ready")
    output_dir = output_dir.absolute()
    # Export outside this checkout so generated input values cannot enter promotion.
    repository_root = HERE.parents[4].resolve()
    _require(not output_dir.resolve().is_relative_to(repository_root),
             "output_inside_source_checkout")
    _require(not output_dir.exists() and not output_dir.is_symlink(), "output_already_exists")
    _require(output_dir.parent.is_dir(), "output_parent_missing")
    with tempfile.TemporaryDirectory(prefix=".development-inputs-", dir=output_dir.parent) as staging:
        stage = Path(staging) / "batch"
        stage.mkdir()
        for filename, payload in outputs.items():
            (stage / filename).write_bytes(payload)
        exported_report = {**report, "inputs_exported": True}
        (stage / "projection-manifest.json").write_bytes(encode(exported_report))
        # Never replace an existing directory, even if it appeared during staging.
        _require(not output_dir.exists() and not output_dir.is_symlink(), "output_already_exists")
        os.rename(stage, output_dir)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--suite", type=Path, default=candidate.SUITE_PATH)
    parser.add_argument("--bindings", type=Path)
    parser.add_argument("--candidate-version", choices=candidate.CANDIDATE_VERSIONS,
                        default=candidate.CANDIDATE_ASSET_VERSION)
    parser.add_argument("--case-id", action="append", required=True)
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--pretty", action="store_true")
    args = parser.parse_args(argv)
    try:
        suite, suite_hash = load_snapshot(args.suite)
        binding_path = args.bindings or (HERE / "development_input_bindings.v2.json"
                         if args.candidate_version == "0.2.2" else BINDINGS_PATH)
        bindings, binding_hash = load_snapshot(binding_path)
        report, outputs = project_batch(suite, bindings, args.case_id,
                                        suite_sha256=suite_hash, binding_sha256=binding_hash,
                                        candidate_version=args.candidate_version)
        if report["status"] == "prepared" and args.output_dir is not None:
            export_batch(args.output_dir, report, outputs)
            report["inputs_exported"] = True
    except ProjectionError as exc:
        report = {"schema_version": "pharma_development_input_projection.v1",
                  "status": "blocked", "reason_code": str(exc), "execution_allowed": False,
                  "inputs_exported": False, "provider_invocations": 0, "values_included": False}
    except (OSError, ValueError, TypeError, KeyError, AttributeError, RecursionError):
        report = {"schema_version": "pharma_development_input_projection.v1",
                  "status": "blocked", "reason_code": "projection_evidence_invalid",
                  "execution_allowed": False, "inputs_exported": False,
                  "provider_invocations": 0, "values_included": False}
    print(json.dumps(report, indent=2 if args.pretty else None, sort_keys=True))
    return 0 if report["status"] == "prepared" else 2


if __name__ == "__main__":
    raise SystemExit(main())

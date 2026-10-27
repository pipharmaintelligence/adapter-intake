"""Top-level SDK workflow coordination, never a nested clinical-child callback.

The host supplies the official registered-asset executor and retains/checkpoints
each accepted run. Only producer run references enter clinical request inputs;
Assets/Core independently verifies and hydrates those outputs at admission.
This module owns semantic selection/normalization and contains no transport.
"""

from copy import deepcopy
from dataclasses import dataclass
from datetime import date
import re

if __package__:
    from .contracts_v0_1_15 import digest, identifier, object_fields, require, safe_json
    from .retained_sources_v0_1_15 import SOURCE_ROLES, UUID
    from .source_bundle_v0_1_15 import terminology_attestation
else:
    from contracts_v0_1_15 import digest, identifier, object_fields, require, safe_json
    from retained_sources_v0_1_15 import SOURCE_ROLES, UUID
    from source_bundle_v0_1_15 import terminology_attestation

NCT = re.compile(r"NCT[0-9]{8}\Z")
PMID = re.compile(r"[1-9][0-9]{0,11}\Z")


class SourceReadUnavailable(RuntimeError):
    """Host-confirmed terminal read unavailability, never an unknown run outcome."""

    def __init__(self, code, *, detail=None):
        require(
            code
            in {
                "source_no_access",
                "source_unavailable",
                "source_rate_limit_exhausted",
                "source_output_unavailable",
            },
            "clinical_source_error_code_invalid",
        )
        self.code = code
        self.detail = {}
        if isinstance(detail, dict):
            for key in (
                "run_uuid",
                "failure_code",
                "failure_cause_code",
                "proof_stage",
            ):
                value = detail.get(key)
                if isinstance(value, str) and re.fullmatch(
                    r"[a-z0-9_:-]{1,120}", value
                ):
                    self.detail[key] = value
        super().__init__(code)


@dataclass(frozen=True)
class SourcePolicy:
    max_source_calls: int = 12
    max_publications: int = 3
    include_terminology: bool = True


class ClinicalSourceWorkflow:
    """Bounded source preparation before clinical execution, with explicit receipts."""

    def __init__(self, execute, *, policy=None):
        self.execute = execute
        self.policy = policy or SourcePolicy()
        require(callable(execute), "clinical_source_executor_unavailable")
        require(
            type(self.policy.max_source_calls) is int
            and 0 <= self.policy.max_source_calls <= 12
            and type(self.policy.max_publications) is int
            and 1 <= self.policy.max_publications <= 3
            and type(self.policy.include_terminology) is bool,
            "clinical_source_policy_invalid",
        )
        self.calls = 0
        self._completed = {}
        self.issues = []
        self.receipts = []
        self.selector_receipts = []

    def _read(self, role, variables):
        asset, version, output, operations, purpose = SOURCE_ROLES[role]
        require(
            variables.get("operation") in operations,
            "clinical_source_operation_invalid",
        )
        safe_json(variables)
        key = digest({"asset": asset, "version": version, "variables": variables})
        if key in self._completed:
            return deepcopy(self._completed[key])
        if self.calls >= self.policy.max_source_calls:
            self.issues.append(
                {"role": role, "code": "clinical_source_call_budget_exhausted"}
            )
            return None
        self.calls += 1
        try:
            response = self.execute(asset, version, output, deepcopy(variables))
        except SourceReadUnavailable as error:
            self.issues.append({"role": role, "code": error.code, **error.detail})
            return None
        response = object_fields(response, {"run_uuid", "result"})
        require(
            isinstance(response["run_uuid"], str)
            and UUID.fullmatch(response["run_uuid"]) is not None,
            "clinical_source_execution_reference_invalid",
        )
        result = response["result"]
        require(
            isinstance(result, dict)
            and result.get("operation") == variables["operation"],
            "clinical_source_operation_mismatch",
        )
        schema = {
            "nusaibah.clinical_trials_lookup": "clinical_trials_lookup.v1",
            "nusaibah.pubmed_evidence": "pubmed_evidence.v1",
        }.get(asset)
        require(
            schema is None or result.get("schema_version") == schema,
            "clinical_source_schema_mismatch",
        )
        states = (
            {"ok", "partial", "not_found"}
            if asset == "umls_terminology"
            else {"completed", "no_match"}
        )
        require(
            isinstance(result.get("status"), str) and result["status"] in states,
            "clinical_source_not_terminal",
        )
        rows = result.get("records", [])
        require(
            isinstance(rows, list)
            and len(rows) <= 50
            and all(isinstance(row, dict) for row in rows),
            "clinical_source_records_invalid",
        )
        if "record_count" in result:
            require(
                type(result["record_count"]) is int
                and result["record_count"] == len(rows),
                "clinical_source_record_count_mismatch",
            )
        require(
            result["status"] not in {"no_match", "not_found"} or not rows,
            "clinical_source_empty_status_conflict",
        )
        if asset == "umls_terminology":
            require(result.get("query") == variables, "clinical_source_query_mismatch")
            terminology_attestation(result)
        if "nct_id" in variables and asset == "nusaibah.clinical_trials_lookup":
            require(
                all(row.get("nct_id") == variables["nct_id"] for row in rows),
                "clinical_source_trial_mismatch",
            )
        if "pmid" in variables:
            require(
                all(row.get("pmid") == variables["pmid"] for row in rows),
                "clinical_source_publication_mismatch",
            )
        if "pmids" in variables:
            require(
                all(row.get("pmid") in variables["pmids"] for row in rows),
                "clinical_source_publication_mismatch",
            )
            missing = sorted(set(variables["pmids"]) - {row["pmid"] for row in rows})
            if missing:
                self.issues.append(
                    {
                        "role": role,
                        "code": "clinical_source_records_missing",
                        "pmids": missing,
                    }
                )
        ids = [
            (
                row.get("nct_id")
                if asset.endswith("clinical_trials_lookup")
                else row.get("ui") if asset == "umls_terminology" else row.get("pmid")
            )
            for row in rows
        ]
        require(
            all(isinstance(value, str) for value in ids) and len(ids) == len(set(ids)),
            "clinical_source_record_identity_invalid",
        )
        self.receipts.append(
            {
                "role": role,
                "asset_key": asset,
                "asset_version": version,
                "output_role": output,
                "operation": variables["operation"],
                "run_uuid": response["run_uuid"],
                "record_count": len(rows),
                "result_digest": digest(result),
                "status": result["status"],
            }
        )
        self._completed[key] = deepcopy(response)
        return response

    def _context_search(self, subject, as_of):
        """Literal governed labels only; metadata matches do not resolve a trial."""
        labels = []
        for key in ("product_name", "indication"):
            value = subject.get(key)
            if not isinstance(value, str) or not 0 < len(value.strip()) <= 160:
                return None
            value = value.strip()
            # Parenthetical names/acronyms are common in governed condition
            # labels. Normalize separators only for discovery; preserve every
            # lexical word, the original subject and a digest receipt. Do not
            # remove biological signs, negation or arbitrary unsupported syntax.
            if re.fullmatch(r"[\w _.,:@()'\-]+", value, re.UNICODE) is None:
                return None
            if re.search(r"(?:https?|file):", value, re.IGNORECASE):
                return None
            depth = 0
            for character in value:
                if character == "(":
                    depth += 1
                elif character == ")":
                    depth -= 1
                if not 0 <= depth <= 4:
                    return None
            if depth:
                return None
            normalized = re.sub(r"[()']", " ", value)
            normalized = re.sub(r" +", " ", normalized).strip()
            if not normalized or re.findall(r"\w+", value) != re.findall(
                r"\w+", normalized
            ):
                return None
            if normalized != value:
                receipt = {
                    "field": key,
                    "original_label_digest": digest(value),
                    "search_label_digest": digest(normalized),
                    "policy": "word_preserving_discovery_separators_v1",
                    "source_subject_changed": False,
                    "clinical_identity_assigned": False,
                }
                if receipt not in self.selector_receipts:
                    self.selector_receipts.append(receipt)
            labels.append(normalized)
        return {
            "operation": "article_search",
            "drug": labels[0],
            "condition": labels[1],
            "page_size": self.policy.max_publications,
            "offset": 0,
            "as_of_date": as_of,
        }

    def prepare(self, subject, variables):
        """Use the governed clinical preflight subject, not model-authored identity."""
        require(
            isinstance(subject, dict) and isinstance(variables, dict),
            "clinical_source_selection_invalid",
        )
        for field in ("subject_id", "product_id"):
            require(
                subject.get(field) == variables.get(field),
                "clinical_source_subject_mismatch",
            )
            identifier(subject[field])
        as_of = variables.get("as_of_date")
        require(isinstance(as_of, str), "clinical_source_date_invalid")
        try:
            date.fromisoformat(as_of)
        except ValueError:
            require(False, "clinical_source_date_invalid")
        trials = subject.get("trial_ids")
        require(
            isinstance(trials, list) and len(trials) <= 32,
            "clinical_source_trial_selectors_invalid",
        )
        nct = variables.get("trial_id")
        if nct is not None:
            require(
                isinstance(nct, str)
                and NCT.fullmatch(nct) is not None
                and nct in trials,
                "clinical_source_exact_trial_required",
            )
        else:
            # A missing trial is a declared evidence gap, never a guessed NCT.
            require(not trials, "clinical_source_exact_trial_required")
        refs = {}

        def select(role, values):
            response = self._read(role, values)
            if response is not None:
                refs[role] = {"run_uuid": response["run_uuid"]}
            return response

        search = None
        if nct is not None:
            for role, operation in (
                ("trial_study_result", "study_get"),
                ("trial_results_result", "results_get"),
            ):
                select(role, {"operation": operation, "nct_id": nct})
            search = select(
                "literature_search_result",
                {
                    "operation": "trial_publications",
                    "nct_id": nct,
                    "page_size": self.policy.max_publications,
                    "offset": 0,
                    "as_of_date": as_of,
                },
            )
        else:
            self.issues.append(
                {
                    "code": "clinical_trial_identity_unresolved",
                    "lookup_execution": "not_requested_without_verified_trial",
                }
            )
        # Exact-NCT search remains preferred. A valid empty result can trigger
        # one context search; an unavailable/failed search cannot authorize it.
        if (
            nct is None
            or search is not None
            and not search["result"].get("records", [])
        ):
            selectors = self._context_search(subject, as_of)
            if selectors is not None:
                role = (
                    "literature_search_result"
                    if nct is None
                    else "literature_context_search_result"
                )
                search = select(role, selectors)
            else:
                self.issues.append(
                    {"code": "clinical_context_search_selector_unavailable"}
                )
        pmids = []
        if search is not None:
            for row in search["result"].get("records", []):
                pmid = row.get("pmid")
                require(
                    isinstance(pmid, str) and PMID.fullmatch(pmid) is not None,
                    "clinical_source_publication_selector_invalid",
                )
                if pmid not in pmids:
                    pmids.append(pmid)
            require(
                len(pmids) <= self.policy.max_publications,
                "clinical_source_publication_limit_exceeded",
            )
            coverage = search["result"].get("coverage", {})
            require(isinstance(coverage, dict), "clinical_source_coverage_invalid")
            if coverage.get("has_more"):
                self.issues.append(
                    {
                        "code": "clinical_publication_discovery_bounded",
                        "returned_count": len(pmids),
                    }
                )
        if pmids:
            select(
                "literature_metadata_result",
                {"operation": "article_batch", "pmids": pmids, "as_of_date": as_of},
            )
            for index, pmid in enumerate(pmids, 1):
                select(
                    "literature_abstract_" + str(index) + "_result",
                    {"operation": "abstract_get", "pmid": pmid, "as_of_date": as_of},
                )
                select(
                    "literature_integrity_" + str(index) + "_result",
                    {"operation": "integrity_get", "pmid": pmid, "as_of_date": as_of},
                )
        else:
            self.issues.append({"code": "clinical_no_publication_candidates"})
        if self.policy.include_terminology:
            term = subject.get("product_name")
            if isinstance(term, str) and 0 < len(term.strip()) <= 128:
                select(
                    "terminology_source_result",
                    {
                        "operation": "search",
                        "text": term.strip(),
                        "search_type": "exact",
                        "limit": 3,
                    },
                )
            else:
                self.issues.append(
                    {"code": "clinical_terminology_selector_unavailable"}
                )
        return {
            "schema_version": "clinical_source_preparation.v1",
            "input_references": refs,
            "status": "partial" if self.issues else "prepared",
            "source_receipts": deepcopy(self.receipts),
            "selector_receipts": deepcopy(self.selector_receipts),
            "issues": deepcopy(self.issues),
            "source_calls": self.calls,
            "authority": "retained_references_require_Assets_Core_admission",
            "clinical_execution_submitted": False,
        }

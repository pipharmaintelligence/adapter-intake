"""Top-level, two-product SDK coordination; no nested adapter invocation."""

from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
import re

if __package__:
    from .contracts_v0_1_14 import ASSET_KEY, VERSION, digest, require
    from .source_workflow_v0_1_14 import ClinicalSourceWorkflow
else:
    from contracts_v0_1_14 import ASSET_KEY, VERSION, digest, require
    from source_workflow_v0_1_14 import ClinicalSourceWorkflow


class ProductRangeWorkflow:
    """Each case gets its own durable SDK host and fresh source preparation.

    execute_factory(key, variables) returns an independently checkpointed SDK
    execute function. Only retained producer references cross into case analysis.
    """

    def __init__(self, execute_factory):
        require(callable(execute_factory), "clinical_range_executor_unavailable")
        self.factory = execute_factory

    def run(self, variables, *, analyze=False, prepare_sources=False):
        require(
            type(analyze) is bool and type(prepare_sources) is bool,
            "clinical_range_analysis_flag_invalid",
        )
        require(
            not (analyze and prepare_sources), "clinical_range_execution_mode_conflict"
        )
        selection = {
            **deepcopy(variables),
            "preflight_only": True,
            "memory_mode": "off",
            "enable_refinement": False,
            "supplementary_search": False,
            "prepare_result_for_persistence": False,
            "enable_pharmacological_class": False,
        }
        execute = self.factory("selection", selection)
        response = execute(ASSET_KEY, VERSION, "product_selection", selection)
        plan = response["result"]
        require(
            plan.get("schema_version") == "clinical_product_range_plan.v1",
            "clinical_range_plan_invalid",
        )
        receipt = plan.get("selection_receipt", {})
        require(
            receipt.get("requested_range") == variables["product_index_range"]
            and receipt.get("index_base") == 0
            and receipt.get("end_inclusive") is True,
            "clinical_range_plan_selection_mismatch",
        )
        selected = receipt["selected_product_ids"]
        require(
            len(selected) == len(set(selected))
            and len(selected) == receipt["selected_product_count"],
            "clinical_range_plan_invalid",
        )
        grouped = {pid: [] for pid in selected}
        seen = set()
        for case in plan["cases"]:
            require(
                case["product_id"] in grouped and case["case_id"] not in seen,
                "clinical_range_plan_case_invalid",
            )
            seen.add(case["case_id"])
            require(
                case["variables"].get("product_id") == case["product_id"]
                and case["variables"].get("product_index_digest")
                == receipt["product_index_digest"],
                "clinical_range_plan_case_invalid",
            )
            grouped[case["product_id"]].append(case)

        def product(pid):
            outcomes = []
            for case in grouped[pid]:
                values = deepcopy(case["variables"])
                host = self.factory(case["case_id"], values)
                try:
                    # This check rehydrates the input and rejects snapshot drift
                    # before any paid source or generation invocation for the case.
                    preflight = {
                        **values,
                        "preflight_only": True,
                        "memory_mode": "off",
                        "enable_refinement": False,
                        "supplementary_search": False,
                        "prepare_result_for_persistence": False,
                        "enable_pharmacological_class": False,
                    }
                    scope = host(ASSET_KEY, VERSION, "clinical_intelligence", preflight)
                    require(
                        scope["result"]["subject"]["product_id"] == pid,
                        "clinical_range_case_subject_changed",
                    )
                    if not analyze and not prepare_sources:
                        outcomes.append(
                            {
                                "case_id": case["case_id"],
                                "product_id": pid,
                                "status": "preflight_completed",
                                "run_uuid": scope["run_uuid"],
                                "provider_generation_requested": False,
                                "publication_confirmed": False,
                            }
                        )
                        continue
                    prepared = ClinicalSourceWorkflow(host).prepare(
                        scope["result"]["subject"], values
                    )
                    if prepare_sources:
                        outcomes.append(
                            {
                                "case_id": case["case_id"],
                                "product_id": pid,
                                "status": (
                                    "source_prepared"
                                    if prepared["status"] == "prepared"
                                    else "partial"
                                ),
                                "source_preparation_status": prepared["status"],
                                "source_preparation_issues": deepcopy(
                                    prepared["issues"]
                                ),
                                "source_calls": prepared["source_calls"],
                                "input_references": deepcopy(
                                    prepared["input_references"]
                                ),
                                "source_receipts": deepcopy(
                                    prepared["source_receipts"]
                                ),
                                "provider_generation_requested": False,
                                "publication_confirmed": False,
                            }
                        )
                        continue
                    final = {
                        **values,
                        "preflight_only": False,
                        "memory_mode": variables.get("memory_mode", "preview"),
                        "enable_refinement": variables.get("enable_refinement", True),
                        "supplementary_search": variables.get(
                            "supplementary_search", True
                        ),
                        "prepare_result_for_persistence": variables.get(
                            "prepare_result_for_persistence", True
                        ),
                        "enable_pharmacological_class": False,
                    }
                    result = host(
                        ASSET_KEY,
                        VERSION,
                        "clinical_intelligence",
                        final,
                        references=prepared["input_references"],
                    )
                    dto = result["result"]
                    outcomes.append(
                        {
                            "case_id": case["case_id"],
                            "product_id": pid,
                            "run_uuid": result["run_uuid"],
                            "status": (
                                "partial"
                                if prepared["status"] == "partial"
                                and dto["quality"]["status"] == "completed"
                                else dto["quality"]["status"]
                            ),
                            "scientific_quality_status": dto["quality"]["status"],
                            "source_preparation_status": prepared["status"],
                            "source_preparation_issues": deepcopy(prepared["issues"]),
                            "source_calls": prepared["source_calls"],
                            "evidence_count": len(dto["evidence"]),
                            "publication_confirmed": False,
                            "result_retained_by_sdk_host": True,
                        }
                    )
                except Exception as error:
                    code = getattr(error, "code", None)
                    code = (
                        code
                        if isinstance(code, str)
                        and re.fullmatch(r"[a-z0-9_]{1,120}", code)
                        else "clinical_range_case_requires_reconciliation"
                    )
                    outcomes.append(
                        {
                            "case_id": case["case_id"],
                            "product_id": pid,
                            "status": "needs_attention",
                            "reason_code": code,
                            "resume_requires_same_checkpoint": True,
                            "publication_confirmed": False,
                        }
                    )
                    # Preserve case order: ambiguous acknowledgement or admission
                    # failure is a stop for this product, not a fresh submission.
                    break
            return outcomes

        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(product, selected))
        cases = [case for group in results for case in group]
        failed = bool(plan["blocked_cases"]) or any(
            row["status"] not in {"completed", "preflight_completed", "source_prepared"}
            for row in cases
        )
        return {
            "schema_version": "clinical_product_range_execution.v1",
            "status": (
                "needs_attention"
                if failed
                else (
                    "completed"
                    if analyze
                    else "source_prepared" if prepare_sources else "preflight_completed"
                )
            ),
            "execution_scope": (
                "scientific_analysis"
                if analyze
                else "source_preparation" if prepare_sources else "model_free_preflight"
            ),
            "selection_run_uuid": response["run_uuid"],
            "selection_receipt": receipt,
            "selection_receipt_digest": digest(receipt),
            "cases": cases,
            "blocked_cases": plan["blocked_cases"],
            "workflow_concurrency": 2,
            "memory_writes_authorized": False,
            "publication_confirmed": False,
        }

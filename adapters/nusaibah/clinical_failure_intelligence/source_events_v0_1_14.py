"""Normalize governed clinical_event_source.v1 rows into one clinical_context.v1.

Input hydration/authority belongs to Assets/Core. This pure mapper never opens
files, queries a lake, assigns a clinical cause or writes Dynamic Skill state.
"""

from __future__ import annotations

from datetime import date
import re
from typing import Any

if __package__:
    from .contracts_v0_1_14 import (
        ContractError,
        canonical_bytes,
        digest,
        identifier,
        identifiers,
        iso_date,
        require,
        safe_json,
        text,
    )
else:
    from contracts_v0_1_14 import (
        ContractError,
        canonical_bytes,
        digest,
        identifier,
        identifiers,
        iso_date,
        require,
        safe_json,
        text,
    )

SOURCE_SCHEMA = "clinical_event_source.v1"
CONTEXT_SCHEMA = "clinical_context.v1"
MAX_SOURCE_RECORDS = 1000
MAX_SOURCE_BYTES = 12 * 1024 * 1024
MAX_SELECTED_EVENTS = 32
MAX_LINKS = 32


def _record_object(value: Any) -> dict:
    require(isinstance(value, dict), "clinical_source_record_invalid")
    safe_json(value)
    require(
        value.get("schema_version") == SOURCE_SCHEMA,
        "clinical_source_record_schema_invalid",
    )
    identifier(value.get("event_id"))
    iso_date(value.get("event_date"))
    require(
        value.get("association_scope") == "event_level_not_pairwise_attributed",
        "clinical_source_association_scope_invalid",
    )
    for field in ("products", "indications", "trials"):
        items = value.get(field)
        require(
            isinstance(items, list) and len(items) <= MAX_LINKS,
            "clinical_source_associations_invalid",
        )
        require(
            all(isinstance(item, dict) for item in items),
            "clinical_source_association_invalid",
        )
    require(
        isinstance(value.get("result_text"), str) and len(value["result_text"]) <= 4000,
        "clinical_source_result_text_invalid",
    )
    require(
        isinstance(value.get("screening_label"), str)
        and len(value["screening_label"]) <= 100,
        "clinical_source_screening_invalid",
    )
    return value


def _provenance(envelope: dict, records: list[dict]) -> dict:
    """Validate complete runtime provenance, not a caller-invented lake authority."""
    value = envelope.get("provenance")
    require(isinstance(value, dict), "clinical_source_governed_provenance_required")
    safe_json(value)
    require(value.get("complete") is True, "clinical_source_incomplete")
    require(
        type(value.get("record_count")) is int
        and value["record_count"] == len(records),
        "clinical_source_count_mismatch",
    )
    require(
        value.get("access_mode")
        in {
            "file_object",
            "partition_file",
            "materialized_query",
            "materialized_retrieval",
        },
        "clinical_source_mode_invalid",
    )
    require(
        isinstance(value.get("source_ref"), str) and bool(value["source_ref"]),
        "clinical_source_reference_missing",
    )
    require(
        isinstance(value.get("sha256"), str)
        and re.fullmatch(r"(?:sha256:)?[0-9a-f]{64}", value["sha256"]) is not None,
        "clinical_source_digest_missing",
    )
    return {
        "source_ref": value["source_ref"],
        "file_sha256": value["sha256"],
        "record_count": value["record_count"],
        "access_mode": value["access_mode"],
        "complete": True,
    }


def _identity_pair(
    entries: list[dict], key: str, label: str, requested: Any
) -> tuple[str | None, str | None]:
    """Select only one event-level association; never Cartesian-join other lists."""
    mapped: dict[str, str | None] = {}
    for item in entries:
        current = identifier(item.get(key))
        require(current not in mapped, "clinical_source_association_duplicate")
        name = item.get(label)
        require(
            name is None or isinstance(name, str),
            "clinical_source_association_label_invalid",
        )
        mapped[current] = name
    if requested is not None:
        selected = identifier(requested)
        require(selected in mapped, "clinical_source_selector_not_found")
    else:
        require(len(mapped) <= 1, "clinical_source_selector_ambiguous")
        selected = next(iter(mapped), None)
    return selected, mapped.get(selected) if selected is not None else None


def _trial_selection(
    entries: list[dict], requested: Any
) -> tuple[str | None, list[str]]:
    """Accept exact NCT records; preserve study names as unresolved leads."""
    nct_ids, leads = [], []
    for row in entries:
        name = text(row.get("value"), maximum=200)
        if row.get("kind") == "nct":
            require(
                len(name) == 11 and name.startswith("NCT") and name[3:].isdigit(),
                "clinical_source_nct_invalid",
            )
            require(name not in nct_ids, "clinical_source_nct_duplicate")
            nct_ids.append(name)
        else:
            leads.append(name)
    if requested is not None:
        chosen = identifier(requested)
        require(chosen in nct_ids, "clinical_source_trial_selector_not_found")
    else:
        require(len(nct_ids) <= 1, "clinical_source_trial_selector_ambiguous")
        chosen = nct_ids[0] if nct_ids else None
    return chosen, leads


def normalize_event_records(values: dict, envelope: Any) -> dict:
    """Build one scoped case from trusted binding-owned records plus semantic IDs.

    The supplied product selector never proves contribution to the source event.
    Missing trials remain absent; a single event ID provides a distinct memory
    scope, instead of inventing an NCT number or merging unrelated cases.
    """
    require(
        isinstance(envelope, dict) and set(envelope) == {"records", "provenance"},
        "clinical_source_envelope_invalid",
    )
    rows = envelope["records"]
    require(
        isinstance(rows, list) and len(rows) <= MAX_SOURCE_RECORDS,
        "clinical_source_count_exceeds_limit",
    )
    safe_json(envelope)
    require(
        len(canonical_bytes(envelope)) <= MAX_SOURCE_BYTES,
        "clinical_source_size_exceeds_limit",
    )
    proof = _provenance(envelope, rows)
    ids = identifiers(
        values["event_ids"], maximum=MAX_SELECTED_EVENTS, allow_empty=False
    )
    product_id = identifier(values.get("product_id"))
    cutoff = iso_date(values["as_of_date"])
    require(
        values["analysis_mode"] == "mechanistic_case",
        "clinical_source_case_mode_required",
    )

    by_id: dict[str, dict] = {}
    for original in rows:
        record = _record_object(original)
        event_id = record["event_id"]
        require(event_id not in by_id, "clinical_source_event_duplicate")
        by_id[event_id] = record
    require(set(ids) <= set(by_id), "clinical_source_event_missing")

    chosen_pair: tuple[str, str, str | None, str | None] | None = None
    assertions, summaries = [], []
    indication_label = ""
    for event_id in ids:
        row = by_id[event_id]
        require(
            date.fromisoformat(row["event_date"]) <= date.fromisoformat(cutoff),
            "clinical_source_event_future",
        )
        found_product, product_name = _identity_pair(
            row["products"], "product_id", "product_name", product_id
        )
        require(found_product == product_id, "clinical_source_product_missing")
        indication_id, current_label = _identity_pair(
            row["indications"],
            "designation_id",
            "designation_label",
            values.get("indication_id"),
        )
        require(
            indication_id is not None
            and current_label is not None
            and current_label.strip(),
            "clinical_source_indication_unresolved",
        )
        trial_id, study_leads = _trial_selection(row["trials"], values.get("trial_id"))
        pair = (product_id, indication_id, trial_id, product_name)
        if chosen_pair is None:
            chosen_pair, indication_label = pair, current_label
        else:
            require(
                pair == chosen_pair and current_label == indication_label,
                "clinical_source_mixed_case_requires_split",
            )
        flags = row.get("quality_flags", [])
        require(
            isinstance(flags, list)
            and all(isinstance(x, str) and len(x) <= 160 for x in flags),
            "clinical_source_quality_flags_invalid",
        )
        product_refs = [identifier(p.get("product_id")) for p in row["products"]]
        indication_refs = [
            identifier(i.get("designation_id")) for i in row["indications"]
        ]
        reported = row["result_text"].strip() or "(no reported result text)"
        statement = (
            "Event "
            + event_id
            + " was entered in a negative clinical-events source on "
            + row["event_date"]
            + "; the source result text reads: "
            + reported
            + ". Product associations: "
            + ", ".join(product_refs)
            + ". Association roles are unresolved; this is not an adjudicated product-specific clinical outcome."
        )
        assertions.append(
            {
                "assertion_id": "SOURCE_EVENT_" + event_id,
                "statement": statement[:8000],
                "source_ref": "governed_event_" + event_id,
                "general_research_observation": "Unverified source-sheet assertion; investigate original study evidence.",
                "example_drugs": [],
                "indicators_to_measure_and_validate": [
                    "Study identity",
                    "Endpoint result",
                    "Product attribution",
                ],
            }
        )
        summaries.append(
            {
                "event_id": event_id,
                "event_date": row["event_date"],
                "reported_text": reported[:2000],
                "reported_screening_label": row["screening_label"],
                "reported_phase": row.get("phase"),
                "reported_sponsor": row.get("sponsor"),
                "selected_product_id": product_id,
                "all_product_ids": product_refs,
                "selected_indication_id": indication_id,
                "all_indication_ids": indication_refs,
                "selected_trial_id": trial_id,
                "study_name_leads": study_leads[:16],
                "association_scope": "event_level_not_pairwise_attributed",
                "quality_flags": list(flags),
                "source_record_digest": digest(row),
            }
        )

    assert chosen_pair is not None
    _, indication_id, trial_id, product_name = chosen_pair
    require(
        trial_id is not None or len(ids) == 1,
        "clinical_source_unreported_trial_requires_single_event",
    )
    scope = {"indication_id": indication_id, "trial_id": trial_id, "regimen_id": None}
    if trial_id is None:
        scope["event_id"] = ids[0]
    result = {
        "schema_version": CONTEXT_SCHEMA,
        "context_id": "context_"
        + digest(
            {
                "source": proof["file_sha256"],
                "events": ids,
                "product_id": product_id,
                "indication_id": indication_id,
                "trial_id": trial_id,
            }
        ).split(":")[1][:32],
        "subject": {
            "subject_id": values["subject_id"],
            "product_id": product_id,
            "product_name": product_name,
            "pharmacological_group_id": None,
            "indication": indication_label,
            "regimen": None,
            "trial_ids": [trial_id] if trial_id is not None else [],
        },
        "case_scope": scope,
        "event_ids": list(ids),
        "source_assertions": assertions,
        "evidence": [],
        "cohort": None,
        "source_event_metadata": {
            "provenance": proof,
            "events": summaries,
            "clinical_outcome_adjudicated": False,
            "pairwise_attribution_verified": False,
        },
    }
    require(
        len(canonical_bytes(result)) <= 256 * 1024,
        "clinical_context_requires_partitioning",
    )
    return result

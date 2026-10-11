"""Bounded semantic context for pharma research claims in adapter 0.1.21.

The contract makes temporal, relationship, quantitative and observation scope
explicit so downstream Agents cannot silently collapse distinct meanings.
It does not certify factual truth; admitted evidence and independent review
remain separate gates.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from math import isfinite
from typing import Any, Mapping


SCHEMA_VERSION = "pharma_claim_semantic_context.v1"
MAX_TEXT_CHARS = 280

EVENT_STATES = frozenset(
    {
        "not_applicable",
        "announced",
        "agreed",
        "completed",
        "approved",
        "launched",
        "recalled",
        "reported",
        "unknown",
    }
)
OBSERVATION_KINDS = frozenset(
    {
        "not_applicable",
        "observed_event",
        "potential_effect",
        "company_reported",
        "inference",
    }
)
SNAPSHOT_RELATIONS = frozenset(
    {
        "not_applicable",
        "same_snapshot",
        "later_external_update",
    }
)
ENTITY_LABEL_KINDS = frozenset(
    {
        "not_applicable",
        "governed_display_name",
        "external_legal_name",
    }
)

SEMANTIC_RULES = (
    (
        "event_date_vs_publication_date",
        "Verify an event date separately from a publication or announcement date.",
    ),
    (
        "agreement_vs_completion",
        "Represent an agreement separately from a completed transaction.",
    ),
    (
        "current_vs_historical_status",
        "Record status against an explicit as-of date and preserve history.",
    ),
    (
        "commercial_rights_direction",
        "Preserve actor, counterparty, territory and manufacturing responsibility.",
    ),
    (
        "governed_snapshot_vs_later_external_update",
        "Keep the governed snapshot distinct from a later external update.",
    ),
    (
        "governed_display_name_vs_external_legal_identity",
        "Do not treat a governed display label as an adjudicated legal name.",
    ),
    (
        "reported_total_reconciliation",
        "Reconcile components to the reported total or name the remainder.",
    ),
    (
        "potential_harm_vs_observed_event",
        "Separate potential effects from an actually observed event.",
    ),
)
RULE_TEXT_BY_ID = dict(SEMANTIC_RULES)

_FIELDS = {
    "schema_version",
    "event_date",
    "publication_date",
    "status_as_of_date",
    "event_state",
    "observation_kind",
    "actor",
    "counterparty",
    "territory",
    "manufacturing_responsibility",
    "reported_total",
    "component_total",
    "remainder_label",
    "governed_snapshot_relation",
    "entity_label_kind",
}


class ClaimSemanticContractError(ValueError):
    """Value-safe deterministic semantic-context rejection."""

    def __init__(self, *, rule: str, field: str) -> None:
        self.rule = rule
        self.field = field
        super().__init__(rule)


@dataclass(frozen=True)
class ClaimSemanticContext:
    """Canonical semantic distinctions carried with one accepted claim."""

    schema_version: str
    event_date: str | None
    publication_date: str | None
    status_as_of_date: str | None
    event_state: str
    observation_kind: str
    actor: str | None
    counterparty: str | None
    territory: str | None
    manufacturing_responsibility: str | None
    reported_total: float | None
    component_total: float | None
    remainder_label: str | None
    governed_snapshot_relation: str
    entity_label_kind: str

    def public_value(self) -> dict[str, Any]:
        """Return the inert claim field passed to review/downstream stages."""

        return {
            "schema_version": self.schema_version,
            "event_date": self.event_date,
            "publication_date": self.publication_date,
            "status_as_of_date": self.status_as_of_date,
            "event_state": self.event_state,
            "observation_kind": self.observation_kind,
            "actor": self.actor,
            "counterparty": self.counterparty,
            "territory": self.territory,
            "manufacturing_responsibility": self.manufacturing_responsibility,
            "reported_total": self.reported_total,
            "component_total": self.component_total,
            "remainder_label": self.remainder_label,
            "governed_snapshot_relation": self.governed_snapshot_relation,
            "entity_label_kind": self.entity_label_kind,
        }

    @property
    def rule_ids(self) -> tuple[str, ...]:
        """Return procedural review rules activated by the supplied context."""

        result: list[str] = []
        if self.event_date is not None or self.publication_date is not None:
            result.append("event_date_vs_publication_date")
        if self.event_state in {"agreed", "completed"}:
            result.append("agreement_vs_completion")
        if self.status_as_of_date is not None or self.event_state in {
            "launched",
            "approved",
            "completed",
        }:
            result.append("current_vs_historical_status")
        if any(
            value is not None
            for value in (
                self.actor,
                self.counterparty,
                self.territory,
                self.manufacturing_responsibility,
            )
        ):
            result.append("commercial_rights_direction")
        if self.governed_snapshot_relation != "not_applicable":
            result.append("governed_snapshot_vs_later_external_update")
        if self.entity_label_kind != "not_applicable":
            result.append(
                "governed_display_name_vs_external_legal_identity"
            )
        if self.reported_total is not None:
            result.append("reported_total_reconciliation")
        if self.observation_kind in {"potential_effect", "observed_event"}:
            result.append("potential_harm_vs_observed_event")
        return tuple(result)


def validate_claim_semantic_context(value: Any) -> ClaimSemanticContext:
    """Validate exact semantic context without reading or inferring source text."""

    if not isinstance(value, Mapping) or set(value) != _FIELDS:
        raise _error("shape", "semantic_context")
    if value.get("schema_version") != SCHEMA_VERSION:
        raise _error("schema_version", "semantic_context.schema_version")

    event_date = _date_or_none(value.get("event_date"), "event_date")
    publication_date = _date_or_none(
        value.get("publication_date"),
        "publication_date",
    )
    status_as_of_date = _date_or_none(
        value.get("status_as_of_date"),
        "status_as_of_date",
    )
    event_state = _enum(
        value.get("event_state"),
        EVENT_STATES,
        "event_state",
    )
    observation_kind = _enum(
        value.get("observation_kind"),
        OBSERVATION_KINDS,
        "observation_kind",
    )
    snapshot_relation = _enum(
        value.get("governed_snapshot_relation"),
        SNAPSHOT_RELATIONS,
        "governed_snapshot_relation",
    )
    entity_label_kind = _enum(
        value.get("entity_label_kind"),
        ENTITY_LABEL_KINDS,
        "entity_label_kind",
    )

    actor = _text_or_none(value.get("actor"), "actor")
    counterparty = _text_or_none(value.get("counterparty"), "counterparty")
    territory = _text_or_none(value.get("territory"), "territory")
    manufacturing = _text_or_none(
        value.get("manufacturing_responsibility"),
        "manufacturing_responsibility",
    )
    reported_total = _number_or_none(
        value.get("reported_total"),
        "reported_total",
    )
    component_total = _number_or_none(
        value.get("component_total"),
        "component_total",
    )
    remainder_label = _text_or_none(
        value.get("remainder_label"),
        "remainder_label",
    )

    if event_state in {"approved", "launched", "completed", "recalled"}:
        if event_date is None:
            raise _error("event_date_required", "event_date")
    if event_state in {"announced", "agreed"} and publication_date is None:
        raise _error("publication_date_required", "publication_date")

    relationship = (actor, counterparty, territory, manufacturing)
    if any(item is not None for item in relationship):
        if actor is None:
            raise _error("relationship_actor_required", "actor")
        if counterparty is None:
            raise _error("relationship_counterparty_required", "counterparty")
        if territory is None:
            raise _error("relationship_territory_required", "territory")

    if (reported_total is None) != (component_total is None):
        raise _error("quantitative_pair_required", "reported_total")
    if (
        reported_total is not None
        and component_total is not None
        and component_total > reported_total
    ):
        raise _error("component_total_exceeds_reported", "component_total")
    if (
        reported_total is not None
        and component_total is not None
        and reported_total != component_total
        and remainder_label is None
    ):
        raise _error("remainder_label_required", "remainder_label")
    if reported_total is None and remainder_label is not None:
        raise _error("remainder_without_total", "remainder_label")

    if snapshot_relation == "later_external_update" and status_as_of_date is None:
        raise _error("external_update_date_required", "status_as_of_date")

    return ClaimSemanticContext(
        schema_version=SCHEMA_VERSION,
        event_date=event_date,
        publication_date=publication_date,
        status_as_of_date=status_as_of_date,
        event_state=event_state,
        observation_kind=observation_kind,
        actor=actor,
        counterparty=counterparty,
        territory=territory,
        manufacturing_responsibility=manufacturing,
        reported_total=reported_total,
        component_total=component_total,
        remainder_label=remainder_label,
        governed_snapshot_relation=snapshot_relation,
        entity_label_kind=entity_label_kind,
    )


def semantic_context_contract() -> dict[str, Any]:
    """Return provider-visible exact fields and reviewed enum values."""

    return {
        "type": "object",
        "exact_fields": True,
        "schema_version": SCHEMA_VERSION,
        "fields": {
            "schema_version": {
                "type": "string",
                "required_value": SCHEMA_VERSION,
            },
            "event_date": {"type": ["string", "null"], "format": "date"},
            "publication_date": {
                "type": ["string", "null"],
                "format": "date",
            },
            "status_as_of_date": {
                "type": ["string", "null"],
                "format": "date",
            },
            "event_state": {
                "type": "string",
                "allowed_values": sorted(EVENT_STATES),
            },
            "observation_kind": {
                "type": "string",
                "allowed_values": sorted(OBSERVATION_KINDS),
            },
            "actor": {"type": ["string", "null"], "max_chars": MAX_TEXT_CHARS},
            "counterparty": {
                "type": ["string", "null"],
                "max_chars": MAX_TEXT_CHARS,
            },
            "territory": {
                "type": ["string", "null"],
                "max_chars": MAX_TEXT_CHARS,
            },
            "manufacturing_responsibility": {
                "type": ["string", "null"],
                "max_chars": MAX_TEXT_CHARS,
            },
            "reported_total": {"type": ["number", "null"], "minimum": 0},
            "component_total": {"type": ["number", "null"], "minimum": 0},
            "remainder_label": {
                "type": ["string", "null"],
                "max_chars": MAX_TEXT_CHARS,
            },
            "governed_snapshot_relation": {
                "type": "string",
                "allowed_values": sorted(SNAPSHOT_RELATIONS),
            },
            "entity_label_kind": {
                "type": "string",
                "allowed_values": sorted(ENTITY_LABEL_KINDS),
            },
        },
        "rule_catalog": [
            {"rule_id": rule_id, "instruction": instruction}
            for rule_id, instruction in SEMANTIC_RULES
        ],
    }


def _date_or_none(value: Any, field: str) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str) or value != value.strip():
        raise _error("date_invalid", field)
    try:
        parsed = date.fromisoformat(value)
    except ValueError:
        raise _error("date_invalid", field) from None
    return parsed.isoformat()


def _text_or_none(value: Any, field: str) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise _error("text_invalid", field)
    text = " ".join(value.split()).strip()
    if not text or len(text) > MAX_TEXT_CHARS:
        raise _error("text_invalid", field)
    if any(ord(character) < 0x20 or ord(character) == 0x7F for character in text):
        raise _error("text_invalid", field)
    return text


def _number_or_none(value: Any, field: str) -> float | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise _error("number_invalid", field)
    number = float(value)
    if not isfinite(number) or number < 0:
        raise _error("number_invalid", field)
    return number


def _enum(value: Any, allowed: frozenset[str], field: str) -> str:
    if not isinstance(value, str) or value not in allowed:
        raise _error("enum_invalid", field)
    return value


def _error(rule: str, field: str) -> ClaimSemanticContractError:
    return ClaimSemanticContractError(rule=rule, field=field)

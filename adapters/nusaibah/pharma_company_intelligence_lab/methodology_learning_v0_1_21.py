"""Review-only procedural methodology proposal for pharma adapter 0.1.21.

The proposal preserves the existing company methodology text byte-for-byte as
its prefix, retains a bounded planner/critic snapshot when it fits, and appends
generic verification lessons identified during the Company 14 review. It
contains no company research facts, changes no Fixed Skill, and grants no
mutation authority.
"""
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import re

try:
    from .claim_semantics_v0_1_21 import SEMANTIC_RULES
except ImportError:  # pragma: no cover - flat intake execution
    from claim_semantics_v0_1_21 import SEMANTIC_RULES


SCHEMA_VERSION = "pharma_methodology_learning_addendum.v1"
MARKER = f"<!-- schema: {SCHEMA_VERSION} -->"
MAX_TOTAL_CHARS = 12000

_EXTRA_LESSONS = (
    (
        "claim_local_withholding",
        "Withhold only a defective claim and affected section prose; preserve unrelated supported work.",
    ),
    (
        "candidate_fact_evidence_selection",
        "Select bounded citations from retained candidate fact IDs before adding secondary evidence.",
    ),
)
LESSONS = (*_EXTRA_LESSONS, *SEMANTIC_RULES)
LESSON_TEXT_BY_ID = dict(LESSONS)


class MethodologyLearningError(ValueError):
    """Value-safe deterministic methodology proposal rejection."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True)
class MethodologyLearningProposal:
    """One bounded, review-only complete section replacement proposal."""

    schema_version: str
    candidate: str
    rule_ids: tuple[str, ...]
    proposal_digest: str
    previous_learning_preserved: bool
    planner_snapshot_included: bool
    changed: bool
    apply_authority: bool
    withheld_reason: str | None = None


def build_methodology_learning_proposal(
    existing_text: str,
    *,
    planner_snapshot: str | None = None,
) -> MethodologyLearningProposal:
    """Preserve existing learning and append reviewed generic lessons.

    The planner snapshot is optional bounded procedural context. It is included
    only as a complete value when the total proposal remains within the existing
    section bound; no snapshot is truncated.
    """

    if not isinstance(existing_text, str):
        raise MethodologyLearningError("methodology_learning_text_invalid")
    if len(existing_text) > MAX_TOTAL_CHARS:
        raise MethodologyLearningError("methodology_learning_text_oversized")
    if planner_snapshot is not None and not isinstance(planner_snapshot, str):
        raise MethodologyLearningError("methodology_planner_snapshot_invalid")

    rule_ids = tuple(rule_id for rule_id, _instruction in LESSONS)
    if len(set(rule_ids)) != len(rule_ids):
        raise MethodologyLearningError("methodology_learning_rule_duplicate")

    addendum = "" if MARKER in existing_text else _render_addendum()
    snapshot = (planner_snapshot or "").strip()
    snapshot_included = False

    candidate = existing_text
    # Repeated canonical headings make Skill section reads ambiguous. Retain
    # the complete planning evidence in the review packet instead of appending
    # a second copy of an existing section into the stored learning proposal.
    headings = set(re.findall(r"^###[ \t]+(.+?)\s*$", existing_text, re.MULTILINE))
    snapshot_headings = set(re.findall(r"^###[ \t]+(.+?)\s*$", snapshot, re.MULTILINE))
    if snapshot and snapshot not in existing_text and not headings.intersection(snapshot_headings):
        proposed = _append(candidate, snapshot + "\n")
        projected = _append(proposed, addendum) if addendum else proposed
        if len(projected) <= MAX_TOTAL_CHARS:
            candidate = proposed
            snapshot_included = True

    withheld_reason = None
    if addendum and len(_append(candidate, addendum)) > MAX_TOTAL_CHARS:
        # Optional learning must not discard completed research or erase prior
        # learning to make room. Withhold this proposal, with an explicit reason.
        candidate = existing_text
        withheld_reason = "methodology_learning_budget_exhausted"
        snapshot_included = False
        rule_ids = tuple(
            rule_id for rule_id, instruction in LESSONS
            if f"- [{rule_id}] {instruction}" in existing_text
        )
    elif addendum:
        candidate = _append(candidate, addendum)

    if len(candidate) > MAX_TOTAL_CHARS:
        raise MethodologyLearningError("methodology_learning_candidate_oversized")
    if not candidate.startswith(existing_text):
        raise MethodologyLearningError("methodology_learning_history_not_preserved")

    return MethodologyLearningProposal(
        schema_version=SCHEMA_VERSION,
        candidate=candidate,
        rule_ids=rule_ids,
        proposal_digest="sha256:" + sha256(candidate.encode("utf-8")).hexdigest(),
        previous_learning_preserved=True,
        planner_snapshot_included=snapshot_included,
        changed=candidate != existing_text,
        apply_authority=False,
        withheld_reason=withheld_reason,
    )


def reviewed_methodology_addendum(existing_text: str) -> str:
    """Project only stored, known procedural rules, never company facts.

    No marker means no reviewed learning is assumed. Exact known rule lines
    avoid forwarding a whole miscellaneous trailing section as methodology.
    The bounded projection is supplied separately from section-specific history.
    """

    if MARKER not in existing_text:
        return ""
    stored = set(existing_text.splitlines())
    lines = [
        f"- [{rule_id}] {instruction}"
        for rule_id, instruction in LESSONS
        if f"- [{rule_id}] {instruction}" in stored
    ]
    return "\n".join(lines)


def _append(existing: str, addition: str) -> str:
    if not addition:
        return existing
    if not existing:
        return addition
    separator = "\n" if existing.endswith("\n") else "\n\n"
    return existing + separator + addition


def _render_addendum() -> str:
    lines = [
        MARKER,
        "### Reviewed Procedural Lessons",
        "",
    ]
    for rule_id, instruction in LESSONS:
        lines.append(f"- [{rule_id}] {instruction}")
    lines.extend(
        [
            "",
            "- review_required: true",
            "- apply_authority: false",
            "- company_facts_included: false",
        ]
    )
    return "\n".join(lines).rstrip() + "\n"

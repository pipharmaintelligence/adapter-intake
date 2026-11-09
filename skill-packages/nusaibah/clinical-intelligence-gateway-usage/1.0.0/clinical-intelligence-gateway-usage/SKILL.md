---
name: clinical-intelligence-gateway-usage
description: Select Clinical Intelligence Gateway operations and interpret blocked, partial and retained results. Use for clinical review requests and follow-ups; scientific analysis remains in separately governed specialist Skills.
---

# Clinical Intelligence Gateway Usage

## overview

Use this gateway for existing assessment review, neutral assessment or explicit all-known/subset class review. Describe capabilities if the available operations or guidance version are unknown. Use only available, admitted operations; guidance cannot grant authority. Read only the usage section needed for the next operation. Do not infer that an installed host Skill or declared runtime Skill is visible through MCP.

## existing_review

Use request_assessment with assessment_mode existing_review, research_objective and as_of_date. Supply a known semantic assessment/product reference when available. The host resolves missing identity conditionally and must verify exact retained producer/version/run/output, checksum, reason-graph lineage, client scope, remaining readable horizon and consumer authority. Never send raw assessment content or storage/binding/actor selectors. If P1 input authority is unavailable, report blocked rather than create or rerun an assessment.

## neutral_assessment

Use request_assessment with assessment_mode neutral_assessment for products lacking a usable prior assessment. Supply research_objective, as_of_date and available semantic product/molecule selectors. Missing failure evidence is not success. Proceed only when the neutral engine, governed ruleset, source roles and budgets are admitted. Arbitrary caller rules are unsupported. Preserve the engine no-publish lifecycle; later retained handoff requires separate host authority.

## class_review

Use request_assessment with assessment_mode class_review, research_objective, as_of_date and an explicit scope_mode. all_known_in_snapshot is relative to a governed dated membership inventory. selected_subset needs explicit product, molecule/name or eligible-case selectors and remains subset-specific. Supplied canonical mapping is context, not authorization; class/group IDs need verified mapping. The host must freeze membership/cases, block extent above 128 without truncation, join independently retained inputs and admit synthesis/critic stages. Do not run recursive children or claim class generalization from failure-only or incomplete coverage.

## get_status

Use get_status with the exact server-issued run_ref from an accepted response. accepted/running is not success; a tool timeout does not authorize another request_assessment. Preserve the run reference and use only server-authorized next actions. Never invent a run ID, switch tenant/actor, or retry a paid workflow to discover status. Durable status/readback remains a separately qualified gateway capability; if not admitted, state that limitation.

## get_result

Use get_result with an authorized existing run_ref when readback is available. Return bounded conclusions, report versions, approved citations and coverage. Recheck scope and retention; an expired or unavailable artifact must not trigger producer replay or retention extension. Preserve the original assessment and graph; corrections are new artifacts. Generic retained verification alone does not prove full clinical content, reviewer authority, permanent node storage or scientific truth.

## result_states

Report membership, selection, execution, evidence, scientific review and class generalization separately. A completed execution may have partial evidence. Handoff accepted means retained/structural eligibility, not scientific accuracy. Preserve source scientific flags, missing/partial/deferred/blocked/outdated/unknown states and denominators. For blocked results explain the safe reason and requested correction; do not invent evidence. Class inference requires the separate scientific gates. Skill improvement is preview-only; guidance never authorizes fixed-Skill edits, Dynamic Skill mutation, clinical execution, publication or deployment.

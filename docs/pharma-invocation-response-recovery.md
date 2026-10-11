# Invocation response recovery — 0.1.25

The observed failure was a nonempty Vertex HTTP 200 / STOP response rejected at
the runtime terminal-object boundary. Existing provider diagnostics did not
retain the exact terminal contract rule. The adapter's schema resolver was
downstream of `invoke_agent(..., on_error="raise")`, so that invocation error
escaped before a business envelope existed.

## One existing diagnostic lane

Assets preserves a static terminal rule in `proof_failure_detail.v1`, through the
trusted session and existing private file IPC. No raw rejected text, provider
body, credentials or storage authority crosses this boundary. The existing
Python/PHP diagnostic validators already support this shape; Core needs no new
schema. Provider validation and retry behavior remain strict and unchanged.

0.1.25 contains only classified `agent_result_json_object_invalid` and
`agent_result_json_value_invalid` failures with the exact trusted Vertex terminal
diagnostic. Unclassified or older-runtime failures, policy, identity, authority,
unsupported-mode and privileged-material rejections still propagate. This is an
explicit adapter behavior; no existing adapter's default failure behavior changes.

## Preserving work

| Failure location | Retained behavior |
|---|---|
| First research pass | Withhold affected role; retain completed sibling claims and their own evidence |
| Portfolio reflection | Retain exact previous validated result and citations; record failed reflection |
| Planner/analysis/critic/synthesis/benchmark | Retain available preparation evidence; skip dependent stages |
| Business JSON backup invocation | Record unresolved result after that sole attempt; never recurse |
| No usable evidence | Complete execution with a truthful incomplete dossier and no invented findings |

The existing issues annex and review packet remain the business status surface.
The new `agent_invocation_response_issues` projection records only company/role/
pass and static diagnostics. Actual failed invocations remain failed in runtime
receipts; workflow completion is not a claim that all Agent calls succeeded.

An unavailable original rejected response is not a repair input. Do not ask a
formatting-only backup to invent its missing facts or borrow citations from a
different role or pass. Existing inspectable business-response repair remains
one reservation per original invocation, subject to unchanged role/company/run
budgets. No new Agent or provider loop is introduced.

## Promotion and verification

1. Land the generic Assets terminal/IPC diagnostic dependency.
2. Promote this exact intake source through `adapter-intake-promote-pr.yml`.
3. Verify materialization preserves all prior packaged identities, helper bytes,
   manifest contracts and support-file hashes. The intake manifest declares the
   current release; the official materializer preserves historical versions.
4. Install the official workflow artifact, identified by source commit and wheel
   hash. Do not patch site-packages or infer contents from the runtime version.
5. Run provider-free installed adapter and real IPC parity fixtures.
6. Register/admit the exact new identity and inspect current Skills.
7. Run one bounded live company case on the intended worker and inspect the
   retained dossier, issues, receipts and actual Skill readback.

Deterministic regressions cover a healthy two-pass preview, first/reflection
failures, sibling preservation, nonresearch roles, a failing one-time backup,
real IPC delivery, strict authority rejection and early apply-mode rejection.
Original production helpers are immutable; version-owned modules compose their
existing evidence validation and review-only orchestration.

## Publication remains governed by actual review

Memory and methodology proposals are review candidates, not committed changes.
This release does not admit an independent review receipt or implement apply.
An incomplete packet withholds its unsafe proposals while retaining inspectable
supported work. Future approved commits must reuse Core's current package upload,
digest/CAS and history lane once per changed Skill. No second persistence path,
invented changelog entry or cross-Skill atomicity claim is introduced.

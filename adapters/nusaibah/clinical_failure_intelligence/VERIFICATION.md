# Verification scope

Local provider-free tests use Python 3.13.5 and explicit synthetic runtime doubles.
The production pi-obs-python-runtime package is not installed in this container.
Read the PR for the exact final source SHA, test count and current CI status.

Checks cover request/response contracts, exact source windows, critic coverage,
cohort denominators, conflict/dependency handling, refinement, budgets, learning
previews, JSON schemas, Python 3.10 grammar and isolated import closure.

Import closure copies only declared files into a temporary root and uses an explicit
test-only Adapter base stub. It is not real SDK or signed-worker evidence. The Fixed
Skill digest is independently computed from the inspected exact-byte algorithm;
the official package validator still needs to run.

The added CI targets Linux/Windows, Python 3.10/3.13, with pinned jsonschema 4.25.1.
Existing broad intake CI is untouched. A workflow file alone does not prove green CI.

NOT RUN LOCALLY: full historical repository suites (no complete clone), real SDK,
official intake/materialization, live source or provider calls, parent-child admission,
mutable Skill, retention/readback, deployment, ECS or durable interruption recovery.
No fixture establishes clinical accuracy; automated supplied-source support is kept
separate from independent external truth and domain-adjudicated qualification.

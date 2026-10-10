# Pharma Agent wait budget — 0.1.19

The company-14 preview `8bac2f10-c1e6-43ba-b6e9-f036535ad7b1` passed missing-memory
preparation but failed in its first methodology planner: three 60-second read
timeouts, no HTTP response, two retry sleeps. This release requests 600 seconds
for **every provider step of all nine roles**, including research formatters and
the one-shot backup resolver. It preserves thinking settings, token limits,
provider/model choices, prompts, schemas and adapter business logic.

Agent versions: planner, portfolio, market, regulatory and critic 1.0.6;
strategic/synthesis 1.0.5; benchmark 1.0.4; resolver 1.0.2. Asset version is 0.1.19.
Intake carries only the current asset version; official promotion preserves older
packaged versions and shared helper bytes. No installed adapter/runtime patching.

## Bounds and meaning

- 600 seconds is a maximum wait **per provider attempt**, including a distinct
  formatting step where declared. It does not force a response to take ten minutes.
- Material expiry and the overall execution deadline can shorten that wait.
- Existing scheduler retries (at most three attempts), jittered backoff, one
  resolver per rejected original response, company count and Agent-call ceilings
  remain. A resolver is not a transport-timeout retry.
- The total asset deadline remains 1,800 seconds. Several slow Agents or retries
  can consume it. Increasing the smoke poll timeout does not extend that deadline.
- A longer wait does not prove that provider latency caused the old timeout or
  repair the separate company-13 terminal JSON/authority-validation failure.

## Required release order

1. Merge generic Core support for 600-second policy/material maxima, preserving
   current defaults/configuration until consumers are ready.
2. Merge generic Assets policy/session/transport/material-consumer support.
3. Merge this intake change and run `adapter-intake-promote-pr.yml` with its exact
   commit against updated Assets main. Validate and merge the generated PR; use
   its official runtime artifact. Runtime package version need not change.
4. Verify all workers that consume Core material support its 600-second lifetime
   before changing the Core-wide material configuration. Old consumers reject
   material exceeding 300 seconds. Do not disrupt older running workers by
   raising the shared lifetime early.
5. Through existing Core operations, set the selected policy's
   `max_timeout_seconds=600` and Core's
   `DLM_PROVIDER_EXECUTION_MATERIAL_TTL_SECONDS=600`, then refresh the actual Core
   service configuration. This is server configuration, not the E client env.
6. Register asset 0.1.19, inspect/provision all exact packaged Agent definitions,
   verify their 12 provider steps request 600, and perform real read-only Skill,
   CompanyContext and provider-admission checks. No paid call is needed here.
7. Only then run the authorized one-company preview and inspect its safe attempt
   timing, retained dossier, portfolio pass trace and before/after canonical state.

## Regression checks

Run the complete pharma deterministic suite, intake promotion-shape check and
frozen evaluation tests. Assert that all provider steps have the requested wait,
all changed immutable chains have new versions, and a normalized comparison with
0.1.18 differs only in version identities and timeouts. Core/Assets regressions
must prove 600-second admission, rejection above the supported maximum, material
refresh between attempts, unchanged defaults and nearer-deadline clamping.

No live success or business-quality claim follows from these offline checks.

# P1 — governed retained-assessment read proof

Status as of **9 November 2026: started, not qualified**. No real producer run,
artifact digest or reviewer input authority has been verified by this task.
This is not evidence that no retained assessment exists.

## Inspection and attempt completed

- Inspected Assets `RetainedAssetOutputInput`, `RunPreviewResultReferenceQuery`,
  `PreviewResultRetention` and `DlmWorkflowArtifactClient` on the previously
  recorded local source revision.
- Confirmed the retained-output path is reference-only at launch: exact
  producer `asset:version`, output role, same client and terminal producer run.
  Hydration rechecks the Core artifact, bounded bytes/checksum and output
  envelope. `verifyForAdmission` additionally checks the read horizon and that
  the retained reference did not change during verification.
- Prepared and attempted an operator-only metadata inventory outside the intake
  package. It selects clinical run/retention metadata and safe reviewer-binding
  projections; it contains no launch, update, source/provider or publication call.
- Default local PHP 8.2 could not bootstrap dependencies requiring PHP 8.4.
  Retried using the repository-documented PHP 8.4 interpreter. Bootstrap ran,
  but the configured database read was unavailable. No candidate rows or
  retained clinical contents were obtained; no Core content read was attempted.
- The safe observation was `inventory_status: unavailable`, reason
  `configured_database_read_unavailable`, `p1_complete: false`, with no business
  values included. A second metadata-only attempt classified the database
  failure as `connection_unavailable`. No raw exception, connection string or credentials were
  emitted by the inventory handler. No database change was requested.

## Retention is distinct from node publication

The existing clinical `clinical_intelligence_records` output is `dry_run`.
That establishes neither a committed governed node record nor the absence of
a separately retained Core artifact. The existing generic retained-input lane
may supply an exact **unexpired Core preview artifact** under its own scoped
contract. Its receipt explicitly does not verify business completion, required
effects, paid retry permission or result-commit permission.

A bounded retained artifact could support the first read-only proof if its
approved scope, exact producer/run/output, retention horizon, complete expected
assessment and consumer authority are demonstrated. It does not become a
permanent canonical DLM node publication. If P1 requires long-lived node-backed
assessment persistence, that must be explicitly established under its separate
governed input policy. Do not create or publish data to bridge that gap here.

Likewise, a regular `AssetInputBinding` row is not the only possible input
contract: the direct retained-output lane is pinned in the consumer manifest.
Checking one database table cannot prove all possible consumer authority.

## Exact evidence required to close P1

| Evidence | Required verification | Current result |
| --- | --- | --- |
| Producer | Exact asset/version, terminal run, original warning/quality state | Unverified |
| Retained input | Governed artifact or approved node-backed source; digest and matching bytes; full expected output role | Unverified |
| Subject and case | Product/molecule/class mapping where applicable; indication/trial; original reason graph and lineage | Unverified |
| Scope and lifetime | Same authorized client; retention readable through declared proof horizon; no cross-scope read | Unverified |
| Consumer | Exact read-only consumer identity and admitted producer/output/input contract, or approved governed child binding | Unverified |
| Read | Existing trusted read path retrieves exact snapshot and emits safe receipt only | Not attempted: inventory unavailable |
| Scientific limits | Original producer quality and uncertified flags preserved; no scientific acceptance inferred | Source contract inspected; actual artifact unverified |

The resulting proof packet must contain safe logical references, digest,
producer/version/run/output role, consumer/input policy, expiry/read horizon,
observation time and a verification disposition. Keep raw assessment/source
content, credentials, internal URLs and storage locations out of the packet.
No synthetic value may fill an unverified proof field.

## Questions required for the next read-only attempt

1. Which approved running Assets/Core environment should the operator inspect,
   and which exact clinical producer run/reference should be checked? The local
   configured database could not be read. Provide environment/run references,
   not credentials or scientific payloads.
2. **Policy resolved by the user:** an existing unexpired Core preview is
   sufficient for the first bounded P1 read proof. It does not establish
   permanent clinical assessment storage. Verify exact consumer authority and
   the remaining readable lifetime; the existing command's initial default
   horizon is 3600 seconds unless the selected environment's policy requires
   otherwise. Do not extend retention to pass the check.

Continue offline P0 review while those inputs remain unresolved. Do not claim
P1 passed, implement scientific Agent reasoning, launch a producer, create a
binding, extend retention, write a node or promote an adapter to manufacture
this proof. P2 remains a separate future read-only executable intake slice.

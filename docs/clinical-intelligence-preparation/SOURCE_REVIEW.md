# Source review — 8 November 2026

Linear: accessible
Repo: accessible
Project source: accessible

## Sources and revisions

| Source | Inspected revision / reference | Result |
| --- | --- | --- |
| User attachment | Clinical Intelligence MCP — Full Orchestration and Pharmacological-Class Review | Requested architecture; preparation authorized, promotion explicitly excluded |
| Second user attachment | Clinical Intelligence MCP — Class Membership & Coverage Design | Both exact scope modes, six completeness dimensions and gateway request/response preparation |
| Follow-up user attachment | PR #174 — Clinical Intelligence Gateway Review & Next Steps, received 9 November | Address 128-item overflow and quality crosswalk; keep draft/unpromoted; begin P1 read-only proof |
| User usage-Skill direction | 9 November: define a ChatGPT-facing Fixed usage contract alongside PR #174 | Design only; distinct internal methodology; one future public gateway; no installation/publication |
| [PI-2086](https://linear.app/pipharma/issue/PI-2086) | Description and 5 November planning refinement comment `c0059bb5-fe49-4026-8d6f-82df2b47f5a8` | Review-only first; one future public gateway; full class path unproven |
| PI-2086 membership decision | 8 November comment `c37b31c7-8f75-4665-8ceb-31463c5df07d` | Both exact scope modes, product × indication × trial/regimen cases and independent coverage dimensions |
| [PI-1751](https://linear.app/pipharma/issue/PI-1751) | Backlog; generic engine/ruleset contract proposal | Dependency, not an existing neutral assessment implementation |
| [UI (DLM + OBS) Solution](https://linear.app/pipharma/project/ui-dlm-obs-solution-9b76c29515e5) | Project description read | DLM authority; DB status projections; async truth; safe refs |
| [adapter-intake main](https://github.com/pipharmaintelligence/adapter-intake/tree/64cc751a89e5470dfce72fa0153ed8569eeae7f5) | `64cc751a89e5470dfce72fa0153ed8569eeae7f5` | Preparation branch base; clinical packages absent from this main snapshot |
| [Clinical intake PR #173](https://github.com/pipharmaintelligence/adapter-intake/pull/173) | Open; head `be55ce6d5ef664f3550e7923353a82f711d0a191`; base branch `codex/clinical-trial-scope-recovery-015` | Clinical 0.1.16 is a stacked source change; do not merge, rebase or duplicate it here |
| [Assets](https://github.com/piusaibah/assets/tree/5b9dbe4216d3a7de7ea9b8972ec4d0332f9fefa9) | Local source `5b9dbe4216d3a7de7ea9b8972ec4d0332f9fefa9` | Same Assets revision used by attachment; packaged implementation inspected |
| [Current Assets main](https://github.com/piusaibah/assets/commit/ec70070eb3cd1111f00c8cb7e855a95e9d60e219) | Connector read and compare: `ec70070eb3cd1111f00c8cb7e855a95e9d60e219`, one commit ahead of local source | Delta covers stream diagnostics/Core continuation and SDK160; clinical package, MCP waiter and registered admission config unchanged; remote config separately re-read |
| DLM Core | Local source `ce42b4a0828beafdeb05b378c57e59a4120d0458` | Available control-plane checkout; no new endpoint or authority certification in this task |
| DLM UI | Local source `4c93869056f10cadc668e8c3f1b2a6df330cb056` | Existing `api/remoteMcpAdmission.ts` and `PlatformRemoteMcpConsentPage.vue` inspected; no UI change proposed |

Local Core/UI revision availability is not a deployed-version assertion. The
user's latest instruction authorizes preparation beyond the earlier planning
comment; it does not authorize implementation of the complete system.

## Verified implementation and gaps

| Capability | Source evidence | Classification |
| --- | --- | --- |
| Failure assessment | Assets `python_runtime/adapters/intake/nusaibah/clinical_failure_intelligence/clinical_failure_intelligence.asset.json`, default `0.1.16` | Packaged, live combination unverified |
| Product range | `range_workflow_v0_1_16.py`; PI-2086 refinement | Bounded SDK host coordination of failure-derived products; not authoritative class inventory |
| Class preview | `orchestration_v0_1_16.py`, `class_extension`, `cross_case_review_required: true`, `write_attempted: false` | Preview only |
| Group memory | `memory_v0_1_16.py` requests `group_memory`; active manifest declares `product_memory` read-only, not `group_memory` | General class read not admitted by this manifest |
| Clinical record output | Active manifest `clinical_intelligence_records.write_mode = dry_run` | Not proof of governed durable published assessment |
| Class statistics | `cohort_v0_1_16.py` | Descriptive denominator calculations; no established class meta-analysis |
| Distributed planning | `ObsExecutionPlanner`, ledger/readback/continuation; `ObsExecutionNonemptyGenericAcceptanceTest.php` | Implemented subset with synthetic/injected authority; no clinical production proof |
| Registered admission | `config/obs_execution_registered_admission.php` | `handlers = []`, `fifo_dispatch_enabled = false` |
| MCP lifecycle | `app/Services/Observability/McpRemote/RemoteMcpRegisteredAssetExecutionService.php`, `RemoteMcpWorkflowTerminalWaiter.php` | Exact run launch followed by bounded terminal wait; no proven arbitrary-duration start/status/readback |
| Neutral assessment | PI-1751 | Proposed generic deterministic engine, `no_publish`; not a substitute failure classifier |
| Usage guidance | Generic Skill Reader development proof, packaged reader 0.1.1 and current clinical manifest | Fixed reads/development reuse exist; Clinical methodology 1.1.0 is internal; gateway usage contract/public ChatGPT consumption remains unqualified |
| Retained review / class synthesis | PI-2086 | Proposed; exact producer/input/critic/output chain unqualified |

No live assessment, source, worker, paid provider, DLM write or Skill mutation
was executed. The preparation examples are synthetic and certify no science.
The dedicated CI definition is offline/provider-free; no remote CI result is
claimed until an actual branch run is observed.

## Closure map for the proposed user journey

| Segment | Existing boundary to reuse | Preparation decision |
| --- | --- | --- |
| Intent and entry | ChatGPT, existing Assets MCP facade | One future published gateway; internal specialists not individually exposed |
| Consent and allowed action | Existing OAuth/consent/admission | Reuse; exact gateway publication remains missing |
| Request | Semantic selectors and optional supplied identity context | Draft request schema; no actor, binding, node, storage or credential selectors |
| Accepted / pending | Existing recorded Assets run | Required durable run ref; current long-running public projection missing |
| Internal work | Frozen product inventory, independent per-product runs, retained readback | Clinical handlers and join qualification missing |
| Feedback and result | Safe bounded status/result projection | Proposed only; no full source/assessment in public MCP messages |
| Recovery | Existing authorized run continuation/readback | No recursive callable children or automatic duplicate provider runs |
| Final state and next action | Versioned review with coverage and unresolved gaps | Review-only result; optional Skill preview separately gated |

No new UI CTA, layout, CSS or navigation is included. Full clinical execution
closure is **incomplete**; this branch prepares its contracts only.

# Product-first memory - development revision 0.1.1

## Primary model

One governed Dynamic Skill per canonical product_id. Product names are display
metadata, not partition identity. The read/update roles are product_memory and
product_memory_update. Indication, trial and regimen remain internal case scopes:

```text
product_memory(product_id=PRODUCT_A)
  # Product PRODUCT_A
  ## Product memory v1
  ## Indication IND_A
     ### Trial TRIAL_1
        #### Regimen REG_1
           ##### Assessment
             Existing dated paragraphs, hypotheses, evidence and limitations
  ## Indication IND_B
     ### Trial TRIAL_2
        #### Regimen REG_2
           ##### Assessment
             Separate case paragraphs: never overwrite TRIAL_1
```

Two events for one case can share an invocation. Different case scopes are split
by the parent, still resolving the same product Skill. The adapter does not add a
queue. Event IDs and source/context revision hashes identify the proposed change;
they are not durable exactly-once receipts. Concurrent writes to one product need
runtime CAS and reconciliation, even when they affect different case sections.

## Default and optional extension

`enable_pharmacological_class` is strictly boolean and defaults to false. Merely
supplying pharmacological_group_id does not enable class work. Default execution
makes no class-memory read or write. Explicit true enables an optional class read
and candidate-reference preview after the primary product delta. Full cross-product
class synthesis and a separate class commit remain unimplemented qualification work.

## Read / evaluate / edit model

```text
New event(s) + canonical product/case IDs
 -> resolve the same product Skill
 -> inspect table of contents and exact case path
 -> rank complete paragraphs by event/query relevance
 -> bounded paragraph packet, never the complete product document
 -> trial / literature / event research
 -> outcome adjudicator -> hypothesis analyst -> scientific evidence critic
 -> product_memory_editor -> paragraph-edit critic
 -> validated product delta plan + JSON + graph + report
 -> CURRENT RELEASE: return preview, write_attempted=false
 -> FUTURE ADMITTED RUNTIME: retain analysis -> CAS apply -> receipt/readback/history
 -> optional class extension, only when enabled
```

The seven logical roles normally require eight calls because the critic has two
separate tasks. An optional four-call scientific refinement shares the existing
12-call budget. Research concurrency remains two; no paid planner or writer with
independent authority is added.

The paragraph selector uses the current SDK's table_of_contents and paragraphs
methods. It sends at most eight complete paragraphs, 3,000 characters per paragraph
and 12,000 characters in total. These are initial reviewed work bounds, not a claim
about universal model limits. Ranking changes prompt selection order, not stored
document order. Oversized/unselected paragraphs are explicitly reported and cannot
be replacement targets. Exact text deduplication is not semantic equivalence.

The view operates after runtime hydration: bounded model context is NOT proof of
partial ZIP/storage retrieval. If package hydration itself exceeds its limit,
qualify the runtime lane separately. Legacy product documents without the Product
memory v1 marker defer for scope-index migration, rather than being treated as empty.

## Change decisions

| Existing state / new event | Delta operation | Preservation rule |
|---|---|---|
| Already represented | keep / no_change | No duplicate paragraph |
| Same case, new supporting detail | enrich_paragraph | Preserve valid prior facts, dates and qualifiers |
| Same case, corrected interpretation | replace_paragraph | Keep relevant earlier attribution and chronology |
| Distinct information in existing case | append_paragraph | Preserve existing order and siblings |
| Missing exact case section | add_section then append_paragraph | Other indications/trials remain intact |
| Unread, stale or ambiguous target | defer | Do not rewrite or assume an empty record |

The editor returns edit_id, operation, target_paragraph_id, before_digest,
section_path, new_text, supporting_item_ids and rationale. Replacements require
an exact selected old paragraph. An independent critic evaluates old/new wording,
scope, accepted evidence and preservation. No delete, move, parent-section upsert
or whole-document replacement is admitted. SDK compilation is available separately
but is not called by the preview flow and never applies a write.

## Exact before / after checklist

| Concern | 0.1.0 | 0.1.1 | Qualification |
|---|---|---|---|
| Primary memory | Pharmacological group | product_id | Fake-runtime tested |
| Repeated product cases | Subject/trial list | Exact indication/trial/regimen case_scope | Mixed trial calls rejected |
| Class default | Group read in case preview | Disabled; explicit true only | Zero default class calls tested |
| Reads | Complete Lessons section, 16k rejection | TOC + ranked complete case paragraphs | Oversized text reported, not cut |
| Update | Reassembled proposed_section | Scoped keep/enrich/replace/append/add delta | Unread/cross-case edits rejected |
| Editorial role | None | product_memory_editor | Versioned prompt and contract |
| Edit quality | Scientific gate only | Second critic checks prior-content preservation | Missing/negative verdict withholds |
| Duplication | Lesson markers | Exact paragraph text digest | Not a semantic dedup guarantee |
| Legacy content | No index migration gate | Explicit defer | No silent empty-state fallback |
| Model instructions | Six generic roles | Seven domain roles; Gemini 3.8 profile | Authored, not live-benchmarked |
| Live mutation | Blocked | Still blocked | Assets child mutation prerequisite |
| Crash recovery | Not qualified | Still not qualified | Runtime stage retention prerequisite |

## Input contract change

Add the optional variable `enable_pharmacological_class: false` (absence also
means false). The binding-owned clinical_context carries product_id in subject
and case_scope with canonical indication_id, trial_id and regimen_id. Do not guess
missing IDs or map unrelated unknown trials to one shared section. memory_mode=off
remains available; memory_mode=apply is rejected before Agent or Skill calls.

## Required Assets work

Admit product read/update roles and the exact product selector; prepare scoped
child inputs and its own Agent capabilities. Register the seven 1.1.0 roles and
Fixed methodology 1.1.0, validate actual Gemini model/tool/schema transport, and
finish safe new-source retrieval. Reuse paragraph SDK methods rather than create a
parallel storage API. Qualify initialization, retained-analysis barrier, CAS,
receipts, fresh readback/history and unchanged sibling bytes before enabling apply.
Class updates are separate optional effects; their failure cannot roll back or
misreport a completed product update. ECS and restart recovery remain separate.

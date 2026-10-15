# Objective

Contain malformed synthesis candidates without losing independently usable
research or publishing unsupported model content.

# System Context

The synthesizer's `memory_candidate` is proposed business JSON, not the stored
company memory. The current profile is assembled from reviewed claims and
paragraphs; Core receives the final document after preparation, retention
admission and baseline checks. An empty verified fact set requires an object
with `fact_ids=[]`. Null is not a valid representation of that object.

The reproduced 0.1.45 defect dereferences non-object candidates before bounded
recovery can handle them. The original response of company 13's failed run was
not retained, so the reproduction does not prove that historical response was null.
Agent contracts set `store_output=false`; usage receipts do not retain research
text, and the range checkpoint contains technical progress rather than business data.

# Approach

Use a version-owned 0.1.46 call chain and restore explicit candidate type
validation. Reuse the existing one-backup contract recovery, paragraph checks,
reviewed-claim fallback and Core Dynamic Skill publication.

# Changes Made

- Missing or non-object candidates produce a structured `memory_candidate` /
  `object_required` diagnostic. The single permitted backup remains bounded.
- Exhausted malformed presentation chunks remain unresolved; valid siblings
  and already reviewed claims continue through existing publication checks.
- The narrative instruction explicitly requires an object with an empty fact
  list when no verified facts are available. It does not authorize new facts.
- New version helpers preserve all historical executable helper bytes and
  reuse the exact prior Agent, source, storage and authority contracts.

# Modularity Impact

The correction belongs to adapter business-response validation. Runtime,
storage, governance and workflow selection stay unchanged. There is no blanket
exception catch, early unvalidated memory write, new paid retry, or local
business-data checkpoint.

# Validation

Provider-free regressions cover null, arrays, strings, numbers, booleans and
missing candidates; a valid empty fact list; completed sibling preservation;
strict identity and runtime failures; and full prepare/apply/readback/history
fixtures with every synthesis candidate null. Verified facts use original
reviewed research statements; safe draft research retains explicit unverified
labels and review annexes. The complete historical suite remains required.

# Risks / Open Questions

Source validation and fixture receipts do not prove live publication. Deliver
through the existing official intake promotion and runtime artifact process.
Do not edit an installed 0.1.45 wheel or rewrite the failed batch checkpoint.
Activating a new version requires exact-version registration/admission and a
separately reconciled recovery plan for the terminal failed run. Intermediate
recovery across an unexpected process crash remains outside this focused fix.

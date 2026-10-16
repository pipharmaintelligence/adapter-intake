## 0.1.49 incomplete publication admission

An incomplete company state can intentionally have no `section_enrichment`,
including when retention admission replaces an oversized result with a compact
diagnostic. Publication now checks that state before reading publishable fields.
It returns the existing explicit withheld receipts with `write_attempted=false`,
`publication_complete=false`, and `continuation_allowed=true`.

This prevents a Python KeyError after successful Agent calls. It does not publish
an incomplete or truncated candidate, retry a Skill write, or claim enrichment
success. Valid company states retain the existing evidence, baseline, publication,
readback and history checks. Actual or uncertain write failures still stop.

The 0.1.48 recovery budgets, models and Agent contracts are preserved. Historical
executables remain unchanged. Use runtime 0.1.107 or later. Offline qualification
does not replace official promotion, exact-version registration and admission, or
live Skill publication and readback evidence.

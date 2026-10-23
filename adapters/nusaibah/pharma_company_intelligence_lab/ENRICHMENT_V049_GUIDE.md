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

The 0.1.48 recovery budgets are preserved. Strategic analysis and evidence criticism
use `gemini-4-argon` with HIGH thinking, JSON output, 32000 tokens and the existing
1200-second timeout. Their exact Agent contracts advance to 1.0.9 and 1.0.16.
Research and other roles retain Flash. Prompt text and deterministic planning are
unchanged; this release adds no extra planning Agent call.

Use runtime 0.1.108 or later for Argon thinking support and bounded authentication
failover. Recognized generation 401 authentication and 403 prediction-IAM denials
exclude that pool member and may select another Core-approved member when signed
pool policy permits it. Existing attempt and deadline limits remain binding.
Unknown/policy denials, Core refresh failures and uncertain writes remain terminal.
Historical executables and Agent contracts remain unchanged. Offline qualification
does not replace official promotion, exact-version registration and admission, or
live Skill publication and readback evidence.

The two changed Agent definitions require exact-version admission after official
delivery and registration. The earlier small Argon probe proves basic access only;
full company enrichment and publication still need live qualification.

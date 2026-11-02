# Clinical 0.1.16: bounded source trial references

A review can cite more trials than the current case contains. Previously source
preparation accepted a review with 64 citations, but the evidence ledger rejected
the complete list at its 32-ID limit before research began.

This immutable release uses one 128-ID limit for source evidence and the ledger,
matching the general bounded identifier-list contract. All 64 review citations
survive unchanged, including their source text, digest, extent and provenance.
The governed case's 32-ID limit and the outcome schema's approved trial IDs do
not change. A literature mention remains a candidate link, never case authority.

When a source window exceeds 128 citations, preparation defers the entire window
with an explicit reason, count, complete-list digest and original source receipt
and pointer. It does not truncate citations or manufacture a smaller source.
Valid sibling windows remain usable. The retained producer output remains the
complete source for later bounded reconciliation; deferral authorizes no replay.

Prompts, model settings, paid budgets, memory policy and publication ownership
are unchanged. Existing versions and manifest entries are preserved. Deployment
requires exact-version promotion, admission, schema qualification and signed
model-free execution before resuming approved research.

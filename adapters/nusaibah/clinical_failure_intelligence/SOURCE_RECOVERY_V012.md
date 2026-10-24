# Clinical 0.1.12 source preparation recovery

Missing NCT IDs no longer prevent governed literature/terminology preparation.
An event-only case keeps its original identity and empty trial list. Exact-NCT
reads remain preferred; a successful empty PubMed NCT search may be followed by
one bounded product-and-indication search. Both discovery receipts are retained.
Literal labels come from the governed preflight subject; no Agent invents a
query, trial association or result. Search hits are candidates, not adjudicated
case identity or clinical outcome evidence. Current limits remain 12 source
executions and three discovered publications per case.

Missing trial identity, empty/bounded discovery and unavailable sources remain
explicit partial states. The range summary cannot label such preparation complete
merely because a downstream scientific output completed. Ambiguous event-level
associations retain snapshot-bound resolution items with their original candidate
sets; they are never expanded into a Cartesian product or automatically assigned.

The UMLS 0.1.1 producer and Core policies remain unchanged. Source failures can
be investigated/recovered with separately checkpointed source attempts; an
unconfirmed acknowledgment must never be automatically repeated. Existing source
and model limits, two-product concurrency, prompt contract 1.7.0 and publication
requirements remain unchanged. All published runtime files and old manifest
versions remain byte-identical.

The public SDK accepts plain business scalars; PubMed owns generated field syntax.
Balanced parenthetical labels and apostrophes are converted to discovery word
separators with a receipt proving that every lexical word is preserved. The source
subject, its negation/qualifiers and case identity remain unchanged. Unsupported
biological signs, URLs, field tags, wildcard/control syntax or malformed labels
remain explicit selector gaps. Search normalization never establishes study or
clinical equivalence. Source-only qualification is available with
`--live --prepare-sources-only`; it cannot be combined with `--analyze`.

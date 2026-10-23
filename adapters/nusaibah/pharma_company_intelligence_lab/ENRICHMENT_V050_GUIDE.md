# Pharma enrichment 0.1.50

The company profile ceiling grows from 96,000 to 384,000 characters. The
workflow report budget grows from 440 to 1,760 KiB and the final business-output
budget from 512 KiB to 2 MiB. These are ceilings, not content quotas.

The default Agent concurrency is three, with the existing hard maximum of three.
Caller overrides of one or two remain supported. Four provider targets remain a
Core routing concern; the adapter does not assign targets, change provider
policies, or multiply retries. Call, time, source-read and token budgets remain.

Role prompts now specify research keywords and substantive subsection coverage.
Research aims for 8–16 distinct findings when evidence supports them, within the
existing response contract. Synthesis preserves all supplied material details in
readable paragraphs. Missing evidence never licenses fabrication or padding.

Memory uses the existing governed Dynamic Skills upload/publication flow:
lake and node resolve to the configured provider instance in Core. No storage
backend is selected by this adapter. Evidence, critic verdicts, verification
labels, fresh package/content baselines, readback and history checks remain.

Workflow-output retention is a separate effect. Optional diagnostic/report
fields are validated and compacted independently of the exact memory candidate.
Compaction keeps publication receipts and emits hashes and byte counts for whole
omitted fields. It neither truncates canonical memory nor changes its publication
decision. Candidate safety failures and ambiguous writes still block publication.

Deploy with the compatible 4 MiB retained-result runtime/Core contract. Core
continues to own manifest/lake credentials, artifact integrity and expiry. This
change does not repair missing historical outputs and does not replay paid runs.

Historical adapter versions and helpers are immutable. Promotion, official
runtime packaging, role admission and idle-worker activation remain required.

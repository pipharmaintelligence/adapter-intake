# Clinical 0.1.11 file-binding compatibility

The approved file binding needs `variables.source_object_id` before Assets hydrates
`clinical_context`. Version 0.1.10 incorrectly classified that transport selector
as a conflicting product/case selector, then dropped it from per-case variables.

Version 0.1.11 permits a positive integer file selector, carries it unchanged into
every case/preflight/source workflow, and leaves file authorization to Assets/Core.
Product/event/indication/trial selector conflicts, complete provenance, source hash
pinning and exact case validation still apply. A product range does not grant
access to another file or a live provider.

The operator config now accepts a `queue_name` on each asset selection. The range
operator requires explicit queues for its Clinical, ClinicalTrials.gov, PubMed and
UMLS dependencies on local_worker. Provision consumers for those queues with the
qualified worker endpoint; no default worker is silently assumed. Successful runs
with warnings remain inspectable through their retained outputs.

Use the versioned entrypoint with `source_object_id: 148` in the variables file.
`0:1` selects two distinct products in first-appearance order; their exact cases
are processed with at most two concurrent product workflows. The default operator
is a local plan; `--live` permits model-free selection/case preflights, and the
separate `--analyze` flag enables paid source/Agent work. Preserve checkpoints.

Scientific outputs are retained. Publication still needs a separately prepared
policy-owned output, descriptor, QC, terminal write receipt and artifact readback.
An approved policy or completed analysis is not publication evidence.

Prompt contracts stay at 1.7.0. Previously published runtime files and manifest
versions are immutable. No new paid execution or clinical publication is part of
this repair's provider-free qualification.

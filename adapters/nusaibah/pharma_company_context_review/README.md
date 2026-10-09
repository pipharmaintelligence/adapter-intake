# Real CompanyContext review (development)

This additive asset is `nusaibah.pharma_company_context_review:0.1.0`.
It consumes one completed, retained `nusaibah.company_scope:0.1.0` output.
It does not change the production intelligence or synthetic evaluation assets,
including their manifests, defaults, sources, contracts or retained evidence.

## Input and authority

Launch inputs contain only a reference and semantic purpose:

```json
{
  "company_context": {"run_uuid": "<completed-scope-run-uuid>"},
  "variables": {"execution_purpose": "company_context_review"}
}
```

The manifest's retained_output policy fixes the producer identity and output
role. Assets checks the client, producer, completed state and artifact expiry.
At execution, Assets reads the original Core-retained artifact and checks its
checksum. Only the run reference is stored in workflow input state. Caller
records, output-role overrides, cross-client references and node_io replacements
are rejected. Python's provenance checks are structural defense, not authority.

The consumer derives one bounded source unit from the admitted CompanyContext.
It reviews what the governed database record says. It neither queries Companies
again nor collects web research. A country identifier is not a country name.
Stored observations do not prove current public truth or source freshness.

## Execution and interpretation

Three specialist roles run in parallel, followed by one exact-span toolkit call,
a semantic evidence verifier, and a global consistency verifier when supported
claims exist. The unchanged role ownership rules prevent identity-only geography
from entering commercial_signals. The same bounded review orchestration and
quote primitives are reused as reviewed source snapshots.

Limits: one company, one source unit/chunk of at most 6000 characters, at most
five logical Agent calls, one toolkit invocation, concurrency three, a 1800-second
deadline, zero repair iterations, zero mutable calls and no publication.
The framework continues to own transport retries and provider authority.

The result is explicitly synthetic=false and preview_only=true. A completed
record review may contain product/commercial/clinical evidence gaps. It is not a
complete company-research dossier, independent adjudication or WP1 release score.
Missing evidence must never be converted to invented findings.

## Delivery and proof

Author in adapter-intake. Use the official promotion workflow for this package
and Company Scope. Do not modify the installed runtime wheel. The Assets generic
query-constraint and retained-output contracts are required server dependencies;
old servers cannot safely run this asset. Before launch, verify exact promoted
files/catalog identities, the approved Companies binding and the E local_worker.

The first live proof is one authorized company: Scope, retained context readback,
this review, retained findings readback, and semantic assessment. Preserve each
run UUID and receipt. Poll an existing run after interruption; never relaunch to
recover retained values. Memory apply, full dumps, ECS and large parallel batches
remain separate qualification gates.

## Output data convention

Scope supplies canonical CompanyContext values in `company_scope_result.records`.
The review returns its complete business report at `evaluation_result.record`,
plus the existing scalar `evaluation_summary`. These are the shared business-data
containers understood by runtime 0.1.104 and preview retention. Literal website
values and evidence quotes remain data; source/authority metadata and credentials
remain separately validated. Historical evaluation output is unchanged.

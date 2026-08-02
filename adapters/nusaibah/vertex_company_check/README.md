# nusaibah.vertex_company_check

Local adapter package for `nusaibah.vertex_company_check:0.1.1`.

The package declares two distinct server-owned capabilities:

- Vertex provider-native online grounding through `@tool.online_search`.
- At most one governed MCP call through the active Core catalogue tuple
  `@mcp.pubmed.search` / `mcp.pubmed` / `pubmed.search`.

## Runtime boundary

Python does not call Vertex, Google Search, PubMed, MCP, OBS, DLM Core, storage,
or a database. The local adapter and `@agent` callable return a deterministic
placeholder using the canonical `company_note` schema. Assets and DLM Core own:

- provider binding and policy admission;
- Vertex transport and grounding;
- MCP declaration allowlisting;
- MCP lease issuance and gateway execution;
- sanitized provider/tool results;
- finalizer, run, result, and checkpoint projections.

## Canonical output

`company_note` contains exactly:

```text
company_id
company_name
generated_note
evidence_summary
confidence
```

Local fixture output is intentionally marked as a placeholder. Version `0.1.1`
opts into the shared, provider-neutral terminal projection:

```json
{
  "agent_input": {
    "roles": [
      "companies"
    ],
    "variables": [
      "company_id"
    ]
  },
  "agent_output": {
    "role": "company_note",
    "content_field": "generated_note",
    "evidence_field": "evidence_summary",
    "confidence_field": "confidence"
  }
}
```

`agent://contracts/nusaibah.vertex-company-check` is an opaque internal
contract locator. It is not a Vertex, OpenAI, Bedrock, Anthropic, MCP, or HTTP
endpoint and carries no credential or provider configuration. Intake permits
this locator only in the declared agent `reference` field.

Only the governed `companies` role and optional `company_id` variable may cross
into the admitted agent prompt. Adding another adapter input does not
automatically authorize forwarding it to a model.

After successful server-owned provider finalization, the complete normalized
provider text replaces `generated_note` verbatim in both canonical output
projections. Company identity fields remain from the governed adapter output;
execution evidence is summarized separately and missing provider confidence is
reported as `not_assessed`. The merger depends only on `provider.output.v1`, so
the platform behavior is the same for Vertex AI, OpenAI, AWS Bedrock,
Anthropic, or another admitted provider. Provider selection and authorization
remain server-owned and do not belong in this adapter package. If this agent
contract later admits multiple provider operations, add the stable
`agent_output.terminal_step_handle`; the platform will not guess a terminal
response from completion order.

## Local validation in DataSpell

Open this folder as the project root and select a Python 3.10+ interpreter with
`pi-obs-python-runtime>=0.1.73` installed.

Run these configurations or their command equivalents:

```powershell
obs-adapter-runner --mode fixture --adapter nusaibah.vertex_company_check:0.1.1 --adapter-root . --request .\fixtures\nusaibah_vertex_company_check.request.json
obs-adapter-profile-runner --adapter-root . --profile .\run_profiles\nusaibah_vertex_company_check.local.json --pretty
obs-asset-diagnose --agent-descriptor .\nusaibah_vertex_company_check.agent.json --capabilities .\capabilities.local.json --pretty
obs-asset-diagnose --quick --adapter-root . --pretty
obs-asset-preflight --adapter-root . --pretty
obs-asset-register --adapter-root . --dry-run --pretty
```

Descriptor readiness proves only that safe search/tool intent is well shaped. It
does not authorize live Vertex or MCP execution.

## Certification limit

The package declares:

```text
tool_call.max_calls = 1
```

Do not increase this value. The current certification scope proves one governed
MCP function-call/function-response round trip only.

## Live proof matrix

PI-1739 requires three separate terminal proofs through the exact registered
asset:

```text
A. Vertex grounding only
B. one governed PubMed MCP call only
C. Vertex grounding plus one governed PubMed MCP call
```

A provider smoke command alone is not the exact packaged-asset proof.

## Safety

Do not add provider credentials, MCP credentials, raw provider/tool responses,
function calls, request headers, URLs, leases, storage paths, object keys, or
backend response bodies to this folder.

# DLM lakes search — separate capability intake candidate

This is a **development-only, independent asset** `nusaibah.dlm_lakes_search@0.1.0`. It is not an upgrade, alias, or rewrite of immutable `nusaibah.abstract_mcp_dlm@0.1.2`.

- Public Remote MCP tool (future): `dlm_search_lakes`.
- Public input: `{"tool_request":{"operation":"lakes.search","q":"oncology","page_size":20}}`.
- Internal runtime role: `dlm_lakes_search` -> separately reviewed `dlm.lakes.search`.
- Internal trusted bridge input: `{"text":"oncology","limit":20}`.
- Trusted result envelope must report `operation=invoke`, exact tool/server/capability identity and execution provenance; projected output is `dlm_mcp_read.v1` with `operation=lakes.search`.
- Keyword search matches authorized lake IDs and names; it does **not** search record contents, use embeddings, or resolve synonyms. It cannot certify complete coverage without trusted pagination evidence.
- No credentials, Core transport, secret references, lake paths, uploads, publication or provider execution in Python.

### ChatGPT tool-use separation

Use `dlm_list_lakes` for **show/list available lakes** without a keyword. Use `dlm_search_lakes` for **find a named lake** using a relevant `q` keyword. Both must appear as independently reviewed publications on the intended MCP surface. Do not confuse a tool description with authorization.

### Explicit readiness hold

Intake metadata is only a candidate. **No** official intake validation, immutable promotion, Assets materialization, signed Core executor registration, capability admission, deployed ECS worker, OAuth consent, public tools/list, or ChatGPT terminal tools/call proof is supplied here. The new Core capability is separately developed in draft PR #309. Do not merge, promote or publish until the exact Core/Assets/adapter contract and scope/negative tests pass. No changes to the original `0.1.2` tree.

# LinkedIn post text adapter

## Purpose

Accept a public LinkedIn post URL, convert it locally to a bounded LinkedIn post reference, and return post text through a server-authorized generic MCP runtime tool.

## Adapter contract

- Asset key: `nusaibah.linkedin_post_extract`
- Input role: `post_request`
- Input field: `post_request.records[].post_url`
- Output role: `post_text`
- Runtime tool role: `linkedin_post_extract`
- Tool handle: `@tool.linkedin_post_extract`
- Capability: `linkedin.posts.extract`

## Runtime input shaping

The public link is validated in the adapter and reduced to a safe LinkedIn URN before tool invocation.

```text
*/posts/example_activity-7483090901934796801-demo
→ urn:li:activity:7483090901934796801
```

The generic bridge receives only:

```python
inputs.invoke_tool(
    "linkedin_post_extract",
    input={"text": "urn:li:activity:7483090901934796801"},
)
```

No raw URL crosses the governed MCP runtime boundary.

## Boundary

The Python adapter does not:

- call LinkedIn directly
- use `requests`, Playwright, Selenium, or browser cookies
- contain LinkedIn credentials or session tokens
- call OBS or DLM Core directly
- select connector URLs or provider headers
- publish or place output in storage

Assets/Core must register and authorize the MCP binding `mcp.linkedin` and capability `linkedin.posts.extract`. The Core profile must select the generic runtime adapter and the managed connector must know how to resolve the safe post reference.

## DataSpell

1. Copy this folder under `pipeline_agent_v1/linkedin_post_extract_adapter`.
2. Open the project root in DataSpell.
3. Select the project virtual environment containing `pi-obs-python-runtime`.
4. Replace the example `post_url` in `fixtures/linkedin_post_extract.request.json` with a public LinkedIn post URL.
5. Run the fixture configuration. Without a runtime tool bridge, the expected terminal status is `failed` with a record reason of `runtime_tool_unavailable`.
6. Use governed `local_worker` execution only after the MCP binding is configured server-side.

## Runtime smoke input

Use `run_profiles/linkedin_post_extract.runtime.inputs.json` with `obs-asset-runtime-smoke`. It is a full Assets inputs object containing the `post_request` role. Do not pass `linkedin_post_extract.inputs.json` to the smoke CLI; that file contains only the records for the local profile runner.

Do not commit private URLs, credentials, cookies, headers, raw provider responses, or runtime authorization values.

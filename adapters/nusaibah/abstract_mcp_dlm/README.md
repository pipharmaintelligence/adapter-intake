# abstract_mcp_dlm

Local lakes-only MCP/DLM tool-call authoring proof.

This folder is a narrowed copy of the DLM MCP toolbox idea. It intentionally keeps only `dlm.lakes.list` and JSON output. It does not call DLM Core, OBS, storage, MCP servers, providers, or HTTP APIs from Python.

## Edit First

- `abstract_mcp_dlm_adapter.py` for local result shaping.
- `abstract_mcp_dlm.agent.json` for agent `tool_call` intent.
- `capabilities.local.json` for safe local capability diagnostics.

## Run

Fixture request proof:

```powershell
E:\nusaibah_projects\demo_asset_project\.venv\Scripts\obs-adapter-runner.exe `
  --mode fixture `
  --adapter-root E:\nusaibah_projects\demo_asset_project\pipeline_agent_v1\abstract_mcp_dlm `
  --adapter nusaibah.abstract_mcp_dlm:0.1.0 `
  --request E:\nusaibah_projects\demo_asset_project\pipeline_agent_v1\abstract_mcp_dlm\fixtures\abstract_mcp_dlm.list_lakes.request.json
```

Profile-runner proof:

```powershell
E:\nusaibah_projects\demo_asset_project\.venv\Scripts\obs-adapter-profile-runner.exe `
  --adapter-root E:\nusaibah_projects\demo_asset_project\pipeline_agent_v1\abstract_mcp_dlm `
  --profile E:\nusaibah_projects\demo_asset_project\pipeline_agent_v1\abstract_mcp_dlm\run_profiles\abstract_mcp_dlm.local.json `
  --env-file E:\nusaibah_projects\demo_asset_project\.env `
  --pretty
```

This profile uses `run_profiles\abstract_mcp_dlm.tool_request.records.json`, a role-level fixture payload. The profile stays local and does not call DLM Core, OBS, MCP, storage, or providers.

## Diagnose

Quick diagnose:

```powershell
E:\nusaibah_projects\demo_asset_project\.venv\Scripts\obs-asset-diagnose.exe `
  --quick `
  --adapter-root E:\nusaibah_projects\demo_asset_project\pipeline_agent_v1\abstract_mcp_dlm `
  --pretty
```

Expected: `status=ready`, `quick.status=ready`, and `network_calls_made=false`.

MCP contract check:

```powershell
E:\nusaibah_projects\demo_asset_project\.venv\Scripts\obs-mcp-contract-check.exe `
  --payload E:\nusaibah_projects\demo_asset_project\pipeline_agent_v1\abstract_mcp_dlm\run_profiles\abstract_mcp_dlm.mcp_contract.json `
  --pretty
```

MCP runtime readiness normalization:

```powershell
E:\nusaibah_projects\demo_asset_project\.venv\Scripts\obs-mcp-runtime-readiness.exe `
  --contract E:\nusaibah_projects\demo_asset_project\pipeline_agent_v1\abstract_mcp_dlm\run_profiles\abstract_mcp_dlm.mcp_contract.json `
  --output E:\nusaibah_projects\demo_asset_project\pipeline_agent_v1\abstract_mcp_dlm\run_profiles\abstract_mcp_dlm.mcp_readiness.json `
  --pretty
```

Without a saved Core/UI runtime lease report this should block as `mcp_runtime_lease_missing`. That is expected: the adapter is not supposed to call DLM Core directly. DLM-backed MCP runtime may use server-owned service configuration; adapter code only declares and consumes governed tool handles.

Doctor with runtime readiness evidence:

```powershell
E:\nusaibah_projects\demo_asset_project\.venv\Scripts\obs-asset-workflow-doctor.exe `
  --workspace E:\nusaibah_projects\demo_asset_project `
  --asset-root pipeline_agent_v1\abstract_mcp_dlm `
  --env-file .env `
  --profile E:\nusaibah_projects\demo_asset_project\pipeline_agent_v1\abstract_mcp_dlm\run_profiles\abstract_mcp_dlm.local.json `
  --profile-runner-report E:\nusaibah_projects\demo_asset_project\pipeline_agent_v1\abstract_mcp_dlm\run_profiles\abstract_mcp_dlm.profile_runner.output.json `
  --mcp-contract-report E:\nusaibah_projects\demo_asset_project\pipeline_agent_v1\abstract_mcp_dlm\run_profiles\abstract_mcp_dlm.mcp_contract.report.json `
  --mcp-readiness-report E:\nusaibah_projects\demo_asset_project\pipeline_agent_v1\abstract_mcp_dlm\run_profiles\abstract_mcp_dlm.mcp_readiness.json `
  --pretty
```
Workflow doctor with MCP evidence:

```powershell
E:\nusaibah_projects\demo_asset_project\.venv\Scripts\obs-asset-workflow-doctor.exe `
  --workspace E:\nusaibah_projects\demo_asset_project `
  --asset-root pipeline_agent_v1\abstract_mcp_dlm `
  --env-file .env `
  --profile E:\nusaibah_projects\demo_asset_project\pipeline_agent_v1\abstract_mcp_dlm\run_profiles\abstract_mcp_dlm.local.json `
  --profile-runner-report E:\nusaibah_projects\demo_asset_project\pipeline_agent_v1\abstract_mcp_dlm\run_profiles\abstract_mcp_dlm.profile_runner.output.json `
  --mcp-contract-report E:\nusaibah_projects\demo_asset_project\pipeline_agent_v1\abstract_mcp_dlm\run_profiles\abstract_mcp_dlm.mcp_contract.report.json `
  --pretty
```

Expected current boundary: local contract ready, manifest substrate ready, adapter update not required, and live proof waiting on a value-safe Core/UI MCP runtime readiness report.

## JSON Enforcement

To confirm JSON enforcement, run the invalid-format fixture. It should return a safe failed tool result with `reason_code=response_format_not_supported`, not a Python exception.

```powershell
E:\nusaibah_projects\demo_asset_project\.venv\Scripts\obs-adapter-runner.exe `
  --mode fixture `
  --adapter-root E:\nusaibah_projects\demo_asset_project\pipeline_agent_v1\abstract_mcp_dlm `
  --adapter nusaibah.abstract_mcp_dlm:0.1.0 `
  --request E:\nusaibah_projects\demo_asset_project\pipeline_agent_v1\abstract_mcp_dlm\fixtures\abstract_mcp_dlm.invalid_response_format.request.json
```

## Boundary

`tool_call` is descriptor intent. Live execution requires Assets/Core approval and a runtime lease. Do not add tokens, URLs, headers, storage paths, raw provider responses, raw tool responses, or raw DLM/Core responses to this project.
## Core/UI Runtime Lease Report Shape

For live proof, save a Core/UI MCP readiness report before running doctor. Minimal safe shape:

```json
{
  "schema_version": "mcp_runtime_lease.v1",
  "safe": true,
  "values_included": false,
  "code": "mcp_vault_runtime_lease_validated",
  "lease": {
    "status": "validated",
    "tool_handle": "@tool.abstract_mcp_dlm",
    "tool_server_ref": "mcp.abstract_dlm",
    "capability_ref": "dlm.lakes.list",
    "allowed_api_handles": ["@tool.abstract_mcp_dlm"]
  }
}
```

This proves server-side MCP readiness only. It must not include runtime access material, transport addresses, raw Core responses, raw tool responses, storage refs, SQL, or backend payloads.

## Live Runtime Bridge Update

This adapter now supports the governed runtime bridge. The manifest declares `runtime_tools.dlm_lakes_list`, and the adapter calls:

```python
inputs.invoke_tool("dlm_lakes_list", input={"text": "list DLM lakes; limit 25"})
```

Local fixture/profile runs without a bridge remain intent-only and return `authority=server_authorized_intent_only`. In governed `local_worker` or ECS execution, Assets should inject the bridge, consume the Core MCP authorization just in time, and the result should return `authority=assets_core_runtime_lease`.

If the DLM UI readiness drawer says the authorization is ready but no runtime lease exists, that is expected before execution. Run workflow doctor; `mcp_runtime_lease_pending` means continue to governed runtime execution, not adapter edits.

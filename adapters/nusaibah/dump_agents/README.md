# Dump Agents Adapter

This folder is a local adapter project for `nusaibah.dump_agents:0.1.0`.

## Edit First

- `dump_agents_adapter.py`: adapter logic.
- `dump_agents_outputs.py`: output shaping helpers.
- `dump_agents.asset.json`: local asset identity and declared input/output roles.
- `dump_agents.authoring.json`: safe authoring contract for node/output intent.
- `run_profiles/dump_agents.dlm.json`: local DLM retrieval profile for DataSpell/devtools.

## Authorization And Node Binding

Authorization does not happen inside this adapter.

| Concern | Owner | This adapter may contain |
|---|---|---|
| OBS API authentication | OBS/assets server and local `.env` transport config | no tokens, no headers |
| DLM retrieval authorization | DLM Core retrieval handle policy | `@retrieval_agents` safe handle only |
| Input node binding | DLM Core + Assets input resolver | logical role `agents` only |
| Output node binding | Assets/Core descriptor and publish policy | safe target intent for `dump_agents_by_agent_id` only |
| Storage/object placement | Core/Assets runtime authority | never in adapter code |

The profile uses:

```json
"retrieval_handle": "@retrieval_agents",
"source_scope": "client_scoped_index"
```

That handle must be configured and authorized in DLM Core. The adapter does not know the database, SQL, storage path, object key, or credentials.

The authoring file declares an output intent for:

```json
"lake_id": "googl123",
"node_key": "dump_agents_by_agent_id"
```

That is safe intent metadata. It is not permission to write. Assets/Core must authorize the descriptor/publish policy before any server-side save can happen.

## Business Reference Fields

Fields such as `website`, `url`, `path`, `storage_path`, `object_key`, and `bucket` may appear as business data in records or outputs. The adapter may inspect, normalize, or clean them as strings.

Do not dereference them. Do not call HTTP, S3, DLM, OBS, SQL, provider APIs, MCP, or crawler endpoints from this adapter. Crawler free mode is a separate declared runtime/capability path, not ordinary adapter code.

## Local DataSpell Run

From PowerShell:

```powershell
E:\nusaibah_projects\demo_asset_project\.venv\Scripts\obs-adapter-profile-runner.exe `
  --adapter-root E:\nusaibah_projects\demo_asset_project\pipeline_agent_v1\dump_agents `
  --profile E:\nusaibah_projects\demo_asset_project\pipeline_agent_v1\dump_agents\run_profiles\dump_agents.dlm.json `
  --env-file E:\nusaibah_projects\demo_asset_project\.env `
  --pretty
```

Expected local success means the adapter can process safely resolved records. It does not mean remote OBS asset execution or output save is authorized.

## Remote Admission

If remote preflight returns `asset_not_registered_or_not_allowlisted`, fix server registration/allowlist/policy. Do not add direct server calls to this adapter.

## Cache And Generated Files

Keep `.obs-cache/`, `.obs-reports/`, `.quarantine/`, notebooks checkpoints, and downloaded scratch files out of git unless intentionally promoted.


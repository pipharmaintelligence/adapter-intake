# nusaibah.document_download_readiness
## Runtime and promotion contract

- `documents` is binding-owned. Fixture/profile modes may load the local fixture, but a live OBS request must use an enabled DLM source binding; sending `documents` inline correctly fails with `input_binding_direct_override_forbidden`.
- This adapter has no runtime-required third-party package; its dedicated interpreter contains the matching OBS runtime wheel and forwards no adapter configuration from `.env`.
- If a future dependency is added, declare and pin it in `adapter.dependencies.json`; never install it into a broad shared environment merely because another asset uses it.
- If a future adapter imports sibling Python helpers, publish the adapter catalog so the complete local import closure is path- and SHA-256-attested. Unlisted or changed helpers fail closed.
- Local discovery does not grant server execution. Promote the reviewed adapter, manifest, dependency contract, helper closure, fixtures, and README into Assets, then atomically publish the runtime and manifest generations.
- Adapter/manifest catalog generation changes refresh at job execution time and do not need a Laravel queue restart. A runtime wheel deployment is different and requires restarting the worker binary once.

This is a local DataSpell/PyCharm example for a document-download crawler intent.
It proves adapter shape, capability declaration, and dependency notes. It does
not download a document and does not accept target URLs, tokens, storage paths,
buckets, object keys, cookies, raw HTML, or raw bytes.

Run direct IDE smoke:

```powershell
E:\nusaibah_projects\demo_asset_project\.venv\Scripts\python.exe E:\nusaibah_projects\demo_asset_project\pipeline_agent_v1\document_download_readiness\document_download_readiness_adapter.py
```

Run fixture mode:

```powershell
E:\nusaibah_projects\demo_asset_project\.venv\Scripts\obs-adapter-runner.exe `
  --mode fixture `
  --adapter nusaibah.document_download_readiness:0.1.0 `
  --adapter-root E:\nusaibah_projects\demo_asset_project\pipeline_agent_v1 `
  --request E:\nusaibah_projects\demo_asset_project\pipeline_agent_v1\document_download_readiness\fixtures\document_download_readiness.request.json
```

Fixture file roles:

- `fixtures\document_download_readiness.inputs.json` is the OBS-style inputs map used by diagnose/preflight.
- `fixtures\document_download_readiness.documents.json` is the per-role local-file payload used by profile mode.
Run profile mode:

```powershell
E:\nusaibah_projects\demo_asset_project\.venv\Scripts\obs-adapter-profile-runner.exe `
  --adapter-root E:\nusaibah_projects\demo_asset_project\pipeline_agent_v1 `
  --profile E:\nusaibah_projects\demo_asset_project\pipeline_agent_v1\document_download_readiness\run_profiles\document_download_readiness.local.json `
  --pretty
```

Run diagnostics:

```powershell
E:\nusaibah_projects\demo_asset_project\.venv\Scripts\obs-asset-diagnose.exe `
  --adapter-root E:\nusaibah_projects\demo_asset_project\pipeline_agent_v1 `
  --asset-key nusaibah.document_download_readiness `
  --asset-version 0.1.0 `
  --inputs-file E:\nusaibah_projects\demo_asset_project\pipeline_agent_v1\document_download_readiness\fixtures\document_download_readiness.inputs.json `
  --profile E:\nusaibah_projects\demo_asset_project\pipeline_agent_v1\document_download_readiness\run_profiles\document_download_readiness.local.json `
  --capabilities E:\nusaibah_projects\demo_asset_project\pipeline_agent_v1\document_download_readiness\capabilities.local.json `
  --dependencies E:\nusaibah_projects\demo_asset_project\pipeline_agent_v1\document_download_readiness\adapter.dependencies.json `
  --pretty
```

To make this live, configure the server-owned crawler/RuntimeAuthority target in
Assets/Core and authorize the capability in the UI. The adapter still receives
only safe resolved inputs and returns safe outputs.

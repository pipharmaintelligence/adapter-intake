# Dump Agents Adapter

This folder is a clean adapter-intake handoff for `nusaibah.dump_agents:0.1.0`.

## Included Files

- `adapter.yaml`: handoff metadata for promotion tooling.
- `dump_agents_adapter.py`: adapter logic.
- `dump_agents_outputs.py`: reviewed output shaping helpers.
- `dump_agents.asset.json`: local asset identity and declared roles.

## Boundary

This folder is source handoff only. Runtime admission, input policy, output policy, and deployment are server-owned decisions.

The adapter code must stay API-blind. It may process sanitized input records and return a safe response envelope. It must not embed environment configuration, local runtime artifacts, generated reports, raw fixtures, notebooks, or downloaded scratch files.

## Promotion

Run the generic intake check before pushing:

```powershell
obs-adapter-intake-check --adapter-yaml .\adapter.yaml --pretty
```

Then the package-side promotion planner can read the same metadata:

```powershell
obs-asset-promote --adapter-yaml .\adapter.yaml --precommit-status passed --pretty
```

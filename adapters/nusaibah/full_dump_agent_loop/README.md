# Full Dump Agent Loop Adapter

`nusaibah.full_dump_agent_loop:0.1.0` creates one bounded JSON projection from agent records already delivered by the runtime.

## Contract

- Input role: `agents`, shaped as an object containing a `records` list.
- Execution control: reserved callable variable `agent_ids`, containing one to three unique string or integer identifiers.
- Output role: `full_dump_agent`.
- Output behavior: returns data to the runtime response only. It does not select a storage target or publish data.

The output retains the request order, reports identifiers that were not present in the delivered records, and projects only the declared agent fields.

## Authority Boundary

The adapter performs deterministic in-memory transformation only.

- Input resolution and authorization remain outside the adapter.
- Output binding and publication remain outside the adapter.
- Runtime substrate selection remains Assets-owned.
- Provider, storage, catalog, governance, and credential authority remain outside Python.

The adapter has no external Python dependencies and does not perform network, filesystem, process, database, provider, storage, catalog, or control-plane operations.

## Safe Example

```python
inputs = {
    "agents": {
        "records": [
            {"id": 101, "agent": "Example A"},
            {"id": 202, "agent": "Example B"},
        ]
    },
    "variables": {
        "agent_ids": [202, 101],
    },
}
```

The runtime may later bind `full_dump_agent` to an authorized output contract. Such binding is not part of this adapter package.

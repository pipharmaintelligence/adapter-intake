# Generic Skill reader

`nusaibah.skill_reader@0.1.0` returns approved instruction content through the
existing `inputs.skill()` and `inputs.dynamic_skill()` interfaces. It has no
provider, network, storage, mutation or DLM discovery capability.

Supply `variables` with `source_kind`, a declared `selector`, and a `read` mode:
`sections` (default), `section`, `resource`, or `document`. Section reads take an
exact heading string or heading path. The public resource argument uses components,
for example `["references", "policy.md"]`, so it stays within the existing safe
variable rules; the reader joins and validates an admitted relative resource.
Optional `expected_digest` checks the Skill document digest. Package/resource
changes must also be assessed using the returned package and snapshot identity. Dynamic `selectors`
must match the consuming publication's declared variable contract.

Text is limited to 8 KiB UTF-8; section inventories to 20 entries. Oversized text
fails instead of being truncated. The result includes model-visible identity,
digest, snapshot evidence, completeness and `retention=workflow_result`.
For a Remote MCP publication, `retained_output_role=skill_result` opts into the
existing temporary Core result artifact and exports only that declared role.
PHP checkpoints retain summaries and the reference; approved text stays in the
artifact until its expiry. Reading also checks producer/client scope and byte
integrity. Only content approved for that audience and retention may be bound
to this reader. A fresh read is required after the artifact expires.
The separately configured Remote MCP envelope budget also applies, including its
visible text and structured projections; a smaller budget can reject a read.

The development manifest pins a synthetic fixed package and a separate read-only
dynamic fixture in an existing development node. It does not expose existing
company memory. Its initial public schema allows no caller partition overrides.
Other source/selector bindings use the same adapter logic and the normal reviewed
manifest/publication process; they cannot be supplied as transport authority.

`capabilities.v0.1.0.json` contains publication templates, not a live publication.
Ordinary intake promotion, registration/admission and final ChatGPT compatibility
testing are required. Public publishing and downloadable Skill artifacts are
separate from returning approved text. This asset does not install a host Skill.

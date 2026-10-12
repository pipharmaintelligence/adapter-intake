# DMS AI Discovery — ChatGPT plugin

Version `1.1.0` of this skills-only plugin owns the generic
`mcp-resource-discovery` skill and the existing `dlm-discovery-orchestration`
binding. The generic skill applies to reviewed MCP resource search contracts,
including projects, collections, documents and jobs. The DLM binding keeps the
existing three operation names and their lake/node scope rules. The plugin
identity stays `dms-dlm-discovery` for continuity.

The Python asset `nusaibah.abstract_mcp_dlm@0.1.1` does not consume this skill.
Neither its `skills[]` nor its `published_skills[]` declares an execution
dependency on this package. Assets adapter promotion and internal Skill
publication do not install it into ChatGPT.

## Distribution

The portable source is this directory: root `plugin.json` and
both `skills/*/SKILL.md` files. Package the directory as a ZIP
with one top-level `dms-dlm-discovery/` folder. Publish/install it through the
normal ChatGPT Plugin Skill mechanism, separately from adapter promotion.
This PR supplies reviewed source; it does not publish or install the plugin.

The package uses the conversation's existing authorized MCP tools. It has no
`mcp.json` or `.app.json`: no verified endpoint or registered app identity is
provided here. Enable the intended DLM connection separately. A missing
connection, missing node tool, or missing schema tool is reported as unavailable;
the skill must not invent a tool or route around access controls.

Before distributing to users, install the plugin in a supported host and
verify that the host discovers its name/description and loads its instructions.
Run the cases below against the intended authorized DLM connection. Source
tests validate packaging and adapter contracts, not actual host instruction
following or live MCP execution.

| Conversation | Expected behavior |
| --- | --- |
| Find Hyser; Hyper is suggested | Ask whether Hyper is intended; do not list its nodes before confirmation. |
| Yes, Hyper | Use Hyper's returned lake_id, even if it differs from its name. |
| Several possible lakes | Ask which candidate; a bare yes must not select the first. |
| Find a misspelled node in Hyper | Search inside the selected lake and confirm its returned node_key. |
| Search coverage is partial/unknown | Explain the limitation; do not claim the resource does not exist. |
| Only the lakes tool is installed | Complete lake discovery and report node/schema tools unavailable. |
| No DLM connection is available | Explain that an authorized connection is needed; do not fabricate results. |
| Inspect a resolved node's schema | Use its lake_id and node_key together; report unavailable schemas honestly. |

The initial MCP publication remains one tool, `dlm_list_lakes`. The plugin
cannot make the other two adapter capabilities visible before their own
publication/connection.

## Optional lake/node source ownership

The same instructions may be authored and maintained as a published Fixed Skill
ZIP in a lake/node through the existing DLM upload and immutable Skill
publication process. The registry pins the exact object, version, package digest,
object checksum and consuming-client visibility. A real Assets Skill consumer
uses the existing `published_skills` declaration and admitted Skill reader.

That source location does not install instructions in ChatGPT. Export a reviewed
snapshot of the Skill into this plugin and use the ordinary host distribution
path. A Fixed Skill ZIP and a plugin ZIP have different package roots: the
internal Skill package has `SKILL.md` at its package root; this plugin has
`plugin.json` and `skills/dlm-discovery-orchestration/SKILL.md`.
Do not substitute the full plugin archive for an internal Skill package.
The existing three DLM discovery tools cannot read either package's content.

See OpenAI's [plugin packaging](https://developers.openai.com/plugins/build/plugins)
and [skill activation](https://developers.openai.com/plugins/concepts/skills)
guides for the owning distribution path. Existing Assets Remote MCP publication
continues to own tool names, descriptions, schemas, authentication and execution.

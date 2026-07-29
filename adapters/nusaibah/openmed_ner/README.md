# OpenMed NER reviewed direct-result intake

Asset identity:

```text
nusaibah.openmed_ner@0.1.0
```

This clean intake folder packages the already validated OpenMed NER adapter for
one reviewed `direct_result` execution path.

## Lifecycle

```text
bounded JSON request
→ reviewed launcher
→ existing OpenMedNerAdapter
→ validated, size-bounded response in caller memory
→ no publish
```

The launcher manifest declares:

```text
execution profile     direct_result
execution substrate   local_worker
output lifecycle      no_publish
self-inspection       disabled: no_admitted_output
Core publication      disabled
maximum response      1 MiB
```

No DLM node or lake is required. The launcher does not register an asset, submit
an Assets queue run, create a run UUID, persist a result file, request a Core
lease, stage output, or publish output.

## Local environment

Run from the dedicated validated interpreter and set these values only in the
local shell or DataSpell Run/Debug configuration:

```text
OPENMED_NER_MODEL_DIR=<local approved checkpoint directory>
OPENMED_NER_DEVICE=cuda
TRANSFORMERS_OFFLINE=1
HF_HUB_OFFLINE=1
```

Do not put the checkpoint path or model files in this intake folder.

## Input file

`--request-file` accepts either:

```json
{
  "records": [
    {
      "record_id": "clinical-note-001",
      "text": "The patient received aspirin."
    }
  ]
}
```

or the full adapter role envelope:

```json
{
  "text_records": {
    "records": [
      {
        "record_id": "clinical-note-001",
        "text": "The patient received aspirin."
      }
    ]
  }
}
```

The launcher reports only record counts during validation-only runs and never
prints input text.

## Intake check

From the `pipeline_agent_v1` project root:

```powershell
python -m devtools.adapter_intake `
    --adapter-yaml openmed_ner_intake\adapter.yaml `
    --pretty
```

Expected:

```text
status: ready
category: adapter_intake_ready
```

## Launcher doctor

```powershell
python -m devtools.asset_launcher doctor `
    --adapter-yaml openmed_ner_intake\adapter.yaml `
    --pretty
```

Expected:

```text
status: ready
category: asset_launcher_doctor_ready
```

## Validation-only command

This reads and bounds the request but does not load the model:

```powershell
python -m devtools.asset_launcher run `
    --adapter-yaml openmed_ner_intake\adapter.yaml `
    --request-file openmed_ner\fixtures\openmed_ner.inputs.json `
    --execution-profile direct_result `
    --skip-publish `
    --pretty
```

## Direct result

With the local model environment variables set:

```powershell
python -m devtools.asset_launcher run `
    --adapter-yaml openmed_ner_intake\adapter.yaml `
    --request-file openmed_ner\fixtures\openmed_ner.inputs.json `
    --execution-profile direct_result `
    --execution-substrate local_worker `
    --pretty
```

A successful response contains:

```text
response_version: 1
status: success
outputs.ner_results: present
```

It contains no `run`, `registration`, node, lake, staging, or publication fields.

## Package boundary

This intake folder contains only declared handoff files plus development tests.
The working fixtures, run profiles, reports, caches, model files, IDE metadata,
and local environment files remain outside the reviewed package.

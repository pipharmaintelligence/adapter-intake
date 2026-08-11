# openFDA Application Lookup Adapter

Local adapter package for a controlled Drugs@FDA Runtime Source lookup.

## Contract

- Asset: `nusaibah.openfda_application_lookup@0.1.0`
- Developer-facing input: `variables.application_number`
- Runtime-resolved role: `openfda_application_runtime.records`
- One semantic result capability: `openfda.application.lookup`
- Result fields: `application_number`, `brand_name`, `submission_status_date`
- Substrates: `local_worker`, `ecs`
- Binding configuration: none
- Output publication: none
- Adapter-owned network/provider authentication: none

The adapter expects trusted runtime infrastructure to resolve the governed
Runtime Source before invocation. It never receives the provider credential,
provider endpoint, request headers, or raw Runtime Source execution material.

## Why there are two input roles

The only human/business input is the application number. `build_live_inputs.py`
takes that value and constructs the technical direct Runtime Source selector
used by OBS. That selector is not an input binding and is replaced by trusted
runtime with `{ "records": [...] }` before the adapter runs.

## Offline fixture test

From this folder in the same virtual environment used by the adapter project:

```powershell
python -m unittest discover -s tests -v
```

If the runtime package is installed, you can also execute the saved request with
the normal fixture runner after copying this folder under the project adapter
root and republishing the adapter catalog.

The fixture data is synthetic and exists only to test adapter behavior; it is
not a copied provider response.

## Build one live input file

```powershell
python .\build_live_inputs.py NDA020164 `
  --output .\run_profiles\openfda_application_lookup.live.inputs.json
```

The helper performs no network calls. It writes the application number and the
safe governed Runtime Source identifier into the launch input. No key, token,
URL, header, or binding is written.

## Expected live flow

```text
application_number
      -> direct Runtime Source selector
      -> OBS/Core authority
      -> trusted runtime helper performs governed openFDA request
      -> normalized records
      -> this adapter
      -> application_lookup result
```

The current live Runtime Source must allow the logical `search` input parameter
for application-number filtering. If that is not enabled, correct the governed
Runtime Source configuration rather than adding HTTP logic to this adapter.

## Not included

- no `capabilities.local.json`
- no input binding file
- no provider credential
- no provider URL
- no output node/publish descriptor
- no HTTP library
- no fallback provider
- no crawler logic

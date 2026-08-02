# SEC Company Reference Adapter

Local, deterministic SEC company-reference adapter development project for PI OBS/DLM asset workflows.

## Runtime ownership contract

- The manifest declares the reserved `variables` object as optional because it is a callable-parameter container, not a binding role. The adapter itself still requires and validates one supported identifier.
- `EDGAR_IDENTITY` is not an OBS, Laravel, queue-worker, `.env`, or environment-binding requirement.
- The reviewed Edgar identity is defined once by `EDGAR_IDENTITY` in `sec_company_reference_adapter.py` and is injected into the EdgarTools client only when `edgartools_invoke` is selected.
- `adapter.dependencies.json` pins `edgartools`; the adapter is bound to its dedicated pre-provisioned interpreter with an empty `pass_environment` list.
- Lazy sibling clients are catalog support files. Their paths and SHA-256 hashes are attested with the main adapter and materialized into the isolated child process only after verification.
- Editing the adapter or an imported helper requires an atomic catalog republish and, for a pre-provisioned adapter, an exact interpreter rebind. It does not require a queue restart. Updating the runtime wheel itself requires one worker binary restart.
- Server execution remains unavailable until this reviewed package is promoted into Assets and both runtime and manifest catalog generations are published.

The current implementation preserves the CIK-based local fixture workflow and adds two mutually exclusive, opt-in provider pathways: runtime-owned SEC requests and EdgarTools invocation. It includes:

* identifier validation and normalisation
* an injectable SEC reference client boundary
* a deterministic local fixture client
* a local developer runner
* a reviewed launcher interface
* launcher diagnostics and input dry-run modes
* fixture-backed `direct_result` execution
* explicit blocking of queued execution and runtime-owned projection execution in the standalone launcher
* a `runtime_request` pathway that consumes a runtime-owned safe projection
* an `edgartools_invoke` pathway that uses the optional EdgarTools library
* explicit no-fallback behaviour between provider pathways
* focused adapter, launcher, and provider-path tests

The local fixture runner performs **no live SEC network access**. The launcher defaults to the local fixture path and can perform a bounded live lookup only when `edgartools_invoke` is explicitly selected. The adapter injects its reviewed identity for both `local_worker` and `ecs`; no OBS environment forwarding is required. The `runtime_request` path never acquires a lease or performs the SEC request inside Python; it consumes only the bounded projection supplied by the governed runtime.

---

## Current status

Asset identity:

```text
key: nusaibah.sec_company_reference
version: 0.1.0
```

Supported identifier:

```text
cik
```

Validated but not implemented:

```text
sec_ticker
```

Supported launcher profile:

```text
direct_result
```

Provider pathways:

```text
local fixture client (existing deterministic development path)
runtime_request (runtime-owned lease/capability; Python consumes safe projection)
edgartools_invoke (explicit optional Python-library path)
```

Automatic provider fallback:

```text
disabled
```

Explicitly blocked:

```text
queued_summary
runtime lease acquisition inside Python
automatic provider fallback
asset registration
Core publishing
```

Current automated validation:

```text
47 passed
```

---

## Project structure

```text
sec_company_reference_asset_worker_safe/
Ã¢â€Å“Ã¢â€â‚¬Ã¢â€â‚¬ fixtures/
Ã¢â€â€š   Ã¢â€Å“Ã¢â€â‚¬Ã¢â€â‚¬ sec_company_reference.cik.request.json
Ã¢â€â€š   Ã¢â€â€Ã¢â€â‚¬Ã¢â€â‚¬ sec_company_reference.cik.expected.json
Ã¢â€Å“Ã¢â€â‚¬Ã¢â€â‚¬ tests/
Ã¢â€â€š   Ã¢â€Å“Ã¢â€â‚¬Ã¢â€â‚¬ test_sec_company_reference_adapter.py
Ã¢â€â€š   Ã¢â€Å“Ã¢â€â‚¬Ã¢â€â‚¬ test_sec_company_reference_launch.py
Ã¢â€â€š   Ã¢â€â€Ã¢â€â‚¬Ã¢â€â‚¬ test_sec_company_reference_provider_paths.py
Ã¢â€Å“Ã¢â€â‚¬Ã¢â€â‚¬ edgartools_sec_company_reference_client.py
Ã¢â€Å“Ã¢â€â‚¬Ã¢â€â‚¬ local_sec_company_reference_client.py
Ã¢â€Å“Ã¢â€â‚¬Ã¢â€â‚¬ runtime_sec_company_reference_client.py
Ã¢â€Å“Ã¢â€â‚¬Ã¢â€â‚¬ run_sec_company_reference_local.py
Ã¢â€Å“Ã¢â€â‚¬Ã¢â€â‚¬ sec_company_reference.asset.json
Ã¢â€Å“Ã¢â€â‚¬Ã¢â€â‚¬ sec_company_reference.launcher.json
Ã¢â€Å“Ã¢â€â‚¬Ã¢â€â‚¬ sec_company_reference_adapter.py
Ã¢â€Å“Ã¢â€â‚¬Ã¢â€â‚¬ sec_company_reference_launch.py
Ã¢â€â€Ã¢â€â‚¬Ã¢â€â‚¬ README.md
```

### File responsibilities

`sec_company_reference_adapter.py`

* validates `cik` and `sec_ticker`
* normalises CIK values to ten digits
* keeps `sec_ticker` resolution explicitly unimplemented
* accepts an injected reference client
* validates client output
* owns the final response envelope, logs, metrics, and output projection

`runtime_sec_company_reference_client.py`

* consumes only a bounded `sec_runtime_response` projection
* performs no network or lease operations
* copies runtime-owned input before returning it
* leaves lease, capability, retry, and request authority with the runtime

`edgartools_sec_company_reference_client.py`

* imports EdgarTools lazily only for `edgartools_invoke`
* receives the reviewed identity from the selected adapter
* resolves CIK identity through `edgar.Company`
* projects only company, ticker, and exchange fields
* performs no publishing, storage, queueing, or fallback

`local_sec_company_reference_client.py`

* reads deterministic local fixture data
* performs no network access
* returns only provider-boundary data
* does not own the final adapter response envelope

`run_sec_company_reference_local.py`

* simple DataSpell/local developer runner
* loads the request fixture
* injects the local fixture client
* prints the adapter response as JSON
* is not the governed launcher contract

`sec_company_reference_launch.py`

* reviewed launcher entry point
* supports diagnostics and runtime checks
* supports hidden-value input dry-run
* supports fixture-backed `direct_result`
* blocks `queued_summary`
* blocks `sec_ticker` resolution
* restricts fixture paths to the configured asset root
* enforces the reviewed direct-result size limit

`sec_company_reference.launcher.json`

* declares the currently admitted launcher capability
* admits fixture-backed direct execution on `local_worker` and explicit EdgarTools execution on `local_worker` or `ecs`
* keeps Core publishing disabled
* keeps queued execution blocked and keeps `runtime_request` runtime-owned

---

## Provider pathways

Provider selection belongs in `inputs.execution`, not in business variables.

### Runtime-owned request pathway

```json
{
  "variables": {
    "cik": "0001114448"
  },
  "execution": {
    "provider_path": "runtime_request"
  },
  "sec_runtime_response": {
    "company": {
      "cik": "0001114448",
      "company_name": "Novartis AG"
    },
    "sec_securities": [
      {
        "ticker": "NVS",
        "exchange": "NYSE"
      }
    ]
  }
}
```

The runtime owns the lease, binding/capability resolution, outbound SEC request, retries, and safe response reduction. The Python adapter receives no lease token, URL, header, credential, or raw provider payload.

Successful output metadata identifies the path:

```json
{
  "source_kind": "governed_sec_runtime_projection",
  "provider_path": "runtime_request"
}
```

### EdgarTools invocation pathway

```json
{
  "variables": {
    "cik": "0001114448"
  },
  "execution": {
    "provider_path": "edgartools_invoke"
  }
}
```

Install the optional dependency only in an approved adapter environment:

```powershell
python -m pip install edgartools==5.43.0
```

The reviewed SEC identity is adapter-owned. Do not add `EDGAR_IDENTITY` to `.env`, the OBS environment binding, the queue worker, or the ECS task definition. Change it only through reviewed adapter source and republish the catalog so the module hash and binding remain exact.

Successful output metadata identifies the path:

```json
{
  "source_kind": "edgartools_company_lookup",
  "provider_path": "edgartools_invoke"
}
```

### No automatic fallback

The selected provider is the only provider invoked. A failed `runtime_request` does not invoke EdgarTools, and a failed `edgartools_invoke` does not consume a runtime projection. A future fallback policy must be explicit and runtime-governed.

---

## DataSpell setup

### 1. Open the project root

In DataSpell, open this folder as the project root:

```text
E:\nusaibah_projects\demo_asset_project\pipeline_agent_v1\
sec_company_reference_asset_worker_safe
```

Do not open only the `tests` or `fixtures` directory.

### 2. Select the Python interpreter

Use the project virtual environment that already runs the tests successfully.

In DataSpell:

```text
File
Ã¢â€ â€™ Settings
Ã¢â€ â€™ Project
Ã¢â€ â€™ Python Interpreter
```

Select the existing `.venv` interpreter.

Do not install dependencies into a shared or runtime-owned interpreter.

### 3. Mark the source root if imports are unresolved

If DataSpell cannot resolve imports such as:

```python
from sec_company_reference_adapter import SecCompanyReferenceAdapter
```

right-click the project root and select:

```text
Mark Directory As
Ã¢â€ â€™ Sources Root
```

### 4. Keep IDE configuration safe

Do not place secrets, credentials, provider URLs, tokens, or headers in:

```text
.idea/
Run configurations
source files
fixture files
launcher manifests
```

The current local fixture workflow does not require environment variables or credentials.

---

## Running the local developer runner

From the project root:

```powershell
python .\run_sec_company_reference_local.py
```

The runner loads:

```text
fixtures\sec_company_reference.cik.request.json
```

and uses:

```text
fixtures\sec_company_reference.cik.expected.json
```

as its local fixture-backed reference source.

Expected top-level result:

```json
{
  "response_version": "1",
  "status": "success"
}
```

The current fixture resolves:

```text
CIK: 0001114448
Company: Novartis AG
Security: NVS
Exchange: NYSE
```

This fixture represents the currently locked local contract. It must not be treated as proof of current production SEC data without separate authoritative verification.

---

## Launcher usage

The governed launcher entry point is:

```text
sec_company_reference_launch.py
```

### Runtime check

```powershell
python .\sec_company_reference_launch.py `
  --runtime-check-only
```

Expected category:

```text
runtime_ready
```

This mode:

* does not require an identifier
* does not read fixtures
* does not perform network access
* does not expose values

### Launcher diagnostics

```powershell
python .\sec_company_reference_launch.py `
  --diagnostics-only
```

Expected category:

```text
launcher_diagnostics_ready
```

Diagnostics report safe capability facts such as:

```text
asset key
asset version
direct-result mode
queued-execution availability
network-call status
```

Diagnostics do not include request or provider values.

### Input dry-run

```powershell
python .\sec_company_reference_launch.py `
  --cik 1114448 `
  --skip-publish
```

Expected category:

```text
governed_launch_inputs_ready
```

This mode validates and normalises the identifier without:

* reading provider fixtures
* exposing the supplied CIK
* running the adapter
* publishing anything
* making network calls

### Fixture-backed direct result

```powershell
python .\sec_company_reference_launch.py `
  --cik 1114448 `
  --execution-profile direct_result
```

The launcher normalises:

```text
1114448
```

to:

```text
0001114448
```

It then uses the approved local fixture client and returns the final adapter response.

### EdgarTools direct result

The adapter already owns the reviewed Edgar identity. Do not set an identity environment variable. Explicitly select the EdgarTools path:

```powershell
python .\sec_company_reference_launch.py `
  --cik 1114448 `
  --provider-path edgartools_invoke `
  --execution-substrate local_worker
```

For ECS, use the same command with `--execution-substrate ecs`. The adapter owns the identity; the launcher never accepts or prints it and never falls back to another provider.

### Runtime-owned request path

The standalone launcher intentionally blocks `runtime_request` because the governed runtime must inject the bounded projection:

```powershell
python .\sec_company_reference_launch.py `
  --cik 1114448 `
  --provider-path runtime_request `
  --execution-substrate ecs
```

Expected blocked category:

```text
runtime_request_requires_runtime_projection_injection
```

### Queued execution

```powershell
python .\sec_company_reference_launch.py `
  --cik 1114448 `
  --execution-profile queued_summary
```

Expected blocked category:

```text
queued_execution_requires_approved_sec_client
```

Queued execution is intentionally unavailable.

### SEC ticker input

```powershell
python .\sec_company_reference_launch.py `
  --sec-ticker NVS `
  --execution-profile direct_result
```

Expected blocked category:

```text
sec_ticker_resolution_not_implemented
```

Ticker validation exists, but ticker-to-CIK resolution is outside the current implementation slice.

---

## DataSpell run configurations

### Local fixture runner

Create a Python run configuration:

```text
Name:
SEC Company Reference - Local Fixture

Script path:
run_sec_company_reference_local.py

Working directory:
project root

Interpreter:
project .venv
```

No parameters or environment variables are required.

### Launcher diagnostics

```text
Name:
SEC Company Reference - Diagnostics

Script path:
sec_company_reference_launch.py

Parameters:
--diagnostics-only

Working directory:
project root
```

### Launcher input dry-run

```text
Name:
SEC Company Reference - Input Dry Run

Script path:
sec_company_reference_launch.py

Parameters:
--cik 1114448 --skip-publish

Working directory:
project root
```

### Launcher direct result

```text
Name:
SEC Company Reference - Direct Result

Script path:
sec_company_reference_launch.py

Parameters:
--cik 1114448 --execution-profile direct_result

Working directory:
project root
```

Do not add secrets or live provider configuration to these run configurations.

---

## Testing

Run the full current suite:

```powershell
python -m pytest `
  .\tests\test_sec_company_reference_adapter.py `
  .\tests\test_sec_company_reference_launch.py `
  .\tests\test_sec_company_reference_provider_paths.py `
  -q
```

Current expected result:

```text
47 passed
```

### Adapter coverage

The adapter tests cover:

* CIK normalisation
* SEC ticker normalisation
* missing identifier rejection
* multiple identifier rejection
* malformed identifier rejection
* default-client safety guard
* deterministic fake-client success
* blocked ticker resolution
* CIK identity mismatch rejection
* malformed company payload rejection
* malformed security payload rejection
* request and expected fixture agreement
* local fixture-client projection
* local runner output

### Launcher coverage

The launcher tests cover:

* runtime readiness
* diagnostics
* hidden-value input dry-run
* fixture-backed direct execution
* blocked queued execution
* blocked ticker resolution
* invalid CIK rejection
* fixture-path containment
* stable JSON output
* network-free launcher behaviour

### Provider-path coverage

The provider-path tests cover:

* explicit `runtime_request` selection
* required runtime safe projection
* no EdgarTools call on the runtime path
* explicit `edgartools_invoke` selection
* no runtime fallback on EdgarTools failure
* adapter-owned Edgar identity injection without environment forwarding
* EdgarTools CIK/name/ticker/exchange projection
* ticker/exchange mismatch rejection
* unsupported provider-path rejection

---

## Response contract

Successful CIK execution returns:

```json
{
  "response_version": "1",
  "status": "success",
  "outputs": {
    "company_reference": {
      "requested_identifier": {
        "kind": "cik",
        "value": "0001114448"
      },
      "company": {
        "cik": "0001114448",
        "company_name": "Novartis AG",
        "identity_status": "resolved"
      },
      "sec_securities": [
        {
          "ticker": "NVS",
          "exchange": "NYSE",
          "relationship": "direct_sec_symbol"
        }
      ],
      "metadata": {
        "source_kind": "governed_sec_reference",
        "security_count": 1
      }
    }
  },
  "logs": [
    {
      "level": "info",
      "message": "Prepared SEC company reference for CIK 0001114448."
    }
  ],
  "metrics": {
    "operation_count": 1,
    "sec_security_count": 1
  }
}
```

The adapter owns:

* response version
* status
* output projection
* requested-identifier projection
* identity status
* relationship labels
* safe logs
* safe metrics

The client owns only bounded provider-boundary data:

```json
{
  "company": {
    "cik": "0001114448",
    "company_name": "Novartis AG"
  },
  "sec_securities": [
    {
      "ticker": "NVS",
      "exchange": "NYSE"
    }
  ]
}
```

---

## Safety and ownership boundaries

### Local adapter owns

* identifier validation
* CIK normalisation
* adapter response projection
* local fixtures
* local tests
* local launcher input validation
* local DataSpell workflow
* local deterministic execution

### Local adapter does not own

* credentials
* authentication headers
* live SEC URLs
* direct OBS calls
* direct DLM/Core calls
* object storage placement
* publishing
* queue submission
* workers
* retries
* finalisers
* asynchronous state transitions
* runtime lease, binding, or capability authority
* automatic provider fallback policy

### Current launcher restrictions

The launcher currently enforces:

```text
network_calls_made: false
values_included: false
queued_execution_enabled: false
Core publishing disabled
maximum direct result: 1 MiB
fixture reads restricted to asset root
```

---

## Error categories

The launcher uses stable, value-safe categories.

Examples:

```text
identifier_required
cik_invalid
sec_ticker_invalid
sec_ticker_resolution_not_implemented
queued_execution_requires_approved_sec_client
fixture_path_outside_asset_root
local_fixture_not_found
local_fixture_invalid_json
direct_result_size_limit_exceeded
```

Blocked launcher responses do not include the supplied CIK or ticker value.

---

## What is not implemented

The following remain intentionally outside the current slice:

* runtime lease acquisition inside Python
* direct `requests` or `httpx` SEC transport inside the adapter
* automatic fallback between runtime and EdgarTools
* ticker-to-CIK lookup
* multiple-company fixture repositories
* queued execution
* asset registration
* Core publishing
* OBS-owned asynchronous execution
* storage or materialisation
* adapter-owned retries or finalisation

Do not add URLs, lease tokens, credentials, raw runtime payloads, or direct HTTP calls to the adapter. The optional EdgarTools client is the only Python-library provider path and receives its reviewed SEC identity from the selected adapter.

---

## Next approved extension point

The next step is controlled environment verification, not another provider implementation:

1. install `edgartools==5.43.0` only in the local adapter virtual environment
2. verify the reviewed adapter-owned identity is injected with no environment forwarding
3. run one bounded CIK smoke test through `edgartools_invoke`
4. verify the result remains within the existing company/security projection
5. verify runtime_request integration separately with a runtime-owned safe projection
6. keep `runtime_request` projection injection runtime-owned and separate from the standalone launcher

Until those checks are approved, keep:

```text
local launcher default = local_fixture
runtime_request = safe projection only
edgartools_invoke = explicit opt-in only
automatic fallback = disabled
queued_summary = blocked
sec_ticker = not implemented
Core publishing = disabled
```

---

## Validation checklist

Before sharing or handing off the project:

```powershell
python -m py_compile `
  .\sec_company_reference_adapter.py `
  .\local_sec_company_reference_client.py `
  .\run_sec_company_reference_local.py `
  .\sec_company_reference_launch.py
```

```powershell
python -m json.tool `
  .\sec_company_reference.asset.json `
  > $null
```

```powershell
python -m json.tool `
  .\sec_company_reference.launcher.json `
  > $null
```

```powershell
python -m json.tool `
  .\fixtures\sec_company_reference.cik.request.json `
  > $null
```

```powershell
python -m json.tool `
  .\fixtures\sec_company_reference.cik.expected.json `
  > $null
```

```powershell
python -m pytest `
  .\tests\test_sec_company_reference_adapter.py `
  .\tests\test_sec_company_reference_launch.py `
  .\tests\test_sec_company_reference_provider_paths.py `
  -q
```

Expected test result:

```text
47 passed
```

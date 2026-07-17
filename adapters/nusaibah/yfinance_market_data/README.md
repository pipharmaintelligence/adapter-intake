# yfinance market-data asset

The registered `0.2.2` adapter accepts bounded variables directly. Its
injectable `YFinanceMarketDataClient` lazily imports `yfinance==1.5.1` only
inside an admitted per-dependency environment; no market-data fixture or MCP
HTTP connector is required.

The adapter performs no OBS, Core, storage, queue, publishing, or credential
work. It returns only the stable `market_data` output contract and converts
provider failures to value-safe error codes.

Asset identity: `nusaibah.yfinance_market_data:0.2.2`

## Supported operations

- `history`
- `snapshot`
- allowlisted `attribute`
- `financial_statement`
- All normalized results include `metadata.quote_currency` when the provider
supplies a valid three-letter quote-currency code. Missing currency metadata
is returned as `null` and does not fail an otherwise successful request.

Financial statements support:

- `income_statement`
- `balance_sheet`
- `cash_flow`
- annual or quarterly frequency
- bounded periods and line items
- optional normalized line-item filtering, such as `total_revenue` or `operating_cash_flow`

Arbitrary `getattr()` is not supported. The unsafe snapshot field `timezone` is intentionally excluded from adapter output.

## Isolated local_worker preparation

Runtime `0.1.70` adds a generic dependency cache keyed by the exact lock,
runtime version, Python version, and platform. After the dependency and network
policy fields are explicitly approved, prewarm the environment once:

```powershell
E:\nusaibah_projects\demo_asset_project\.venv\Scripts\obs-asset-dependency-prepare.exe `
  --adapter-root E:\nusaibah_projects\demo_asset_project\adapter-intake-work `
  --adapter nusaibah.yfinance_market_data:0.2.2 `
  --runtime-artifact C:\xampp\htdocs\assets\python_runtime\dist\pi_obs_python_runtime-0.1.70-py3-none-any.whl `
  --pretty
```

The persistent worker does not need to restart after prewarming. On invocation,
it selects the cached child interpreter for this dependency fingerprint.
Unrelated adapters continue in the shared lightweight runtime and cannot import
the child environment through the registry.

Automatic first-use preparation is opt-in with
`OBS_ASSET_DEPENDENCY_AUTO_PREPARE=1` and remains bounded by
`OBS_ASSET_DEPENDENCY_INSTALL_TIMEOUT_SECONDS`. Prewarming is preferred for
production workers.

## ECS package

Build the per-asset ECS bundle with the same lock:

```powershell
.\python_runtime\tools\build_asset_ecs_runtime.ps1 `
  -PrimaryAdapter nusaibah.yfinance_market_data:0.2.2 `
  -DependencyManifest python_runtime\adapters\intake\nusaibah\yfinance_market_data\adapter.dependencies.json `
  -RuntimeWheel python_runtime\dist\pi_obs_python_runtime-0.1.70-py3-none-any.whl `
  -ImageTag yfinance-market-data-0.2.2 `
  -NoBuild
```

The bundle wheel pins the full declared dependency lock. ECS still requires the
packaged adapter registry entry and an enforced task egress policy.

## Production approval gate

`production_approval` is `approved` for both the SDK dependency and the
runtime egress policy in `adapter.dependencies.json`. Dependency preparation
must still succeed for the exact runtime, lock, Python version, and platform.
The worker then selects that isolated cached environment without restarting the
shared Assets queue.

Because this adapter requires outbound market-data access, the worker service
environment must contain `OBS_ASSET_OUTBOUND_POLICY_ENFORCED=true` after the
operator has actually installed/approved the runtime egress policy. Its absence
fails closed with `dependency_outbound_policy_not_enforced`. Do not use this
setting to claim an egress control that infrastructure has not enforced.

## Direct result invocation (no Assets queue)

Use the manifest-declared direct_result profile when the caller needs the
normalized market-data rows immediately and does not need a recorded Assets
run. The launcher still validates adapter.yaml, the launcher manifest, bounded
variables, the exact dependency lock, the prewarmed child environment, the
outbound-policy gate, and the standard adapter response contract.

~~~powershell
E:\nusaibah_projects\demo_asset_project\.venv\Scripts\obs-asset-launch.exe run --adapter-yaml E:\nusaibah_projects\demo_asset_project\adapter-intake-work\adapters\nusaibah\yfinance_market_data\adapter.yaml --env-file E:\nusaibah_projects\demo_asset_project\.env --execution-profile direct_result --execution-substrate local_worker --set symbol=NVS --set operation=history --set period=5d --set interval=1d --set max_rows=5 --pretty
~~~

The command prints the exact validated adapter response, including
outputs.market_data.data.records. It does not register the asset, submit or poll an
Assets run, send result values to Assets, create a run UUID, or write a result
file. The direct response is caller-memory only and is capped at 1 MiB by this
launcher contract.

Use direct_result for synchronous composition from another Python asset or a
local command. Use queued_summary when the run must be visible in the DLM UI.
These are explicit delivery choices; neither performs a second market-data
request.

Direct execution occurs wherever the launcher or calling asset is running. The
execution_substrate argument supplies context; it does not dispatch a laptop
command to ECS.

## Queue invocation

After approval, packaging, runtime installation, and environment prewarming, use
the normal Assets launcher. No provider URL or fixture file is transferred:

```powershell
E:\nusaibah_projects\demo_asset_project\.venv\Scripts\obs-asset-launch.exe run `
  --adapter-yaml E:\nusaibah_projects\demo_asset_project\adapter-intake-work\adapters\nusaibah\yfinance_market_data\adapter.yaml `
  --env-file E:\nusaibah_projects\demo_asset_project\.env `
  --execution-substrate local_worker `
  --set symbol=NVS `
  --set operation=history `
  --set period=5d `
  --set interval=1d `
  --set max_rows=5 `
  --pretty
```

Financial statement:

```powershell
E:\nusaibah_projects\demo_asset_project\.venv\Scripts\obs-asset-launch.exe run `
  --adapter-yaml E:\nusaibah_projects\demo_asset_project\adapter-intake-work\adapters\nusaibah\yfinance_market_data\adapter.yaml `
  --env-file E:\nusaibah_projects\demo_asset_project\.env `
  --execution-substrate local_worker `
  --set symbol=NVS `
  --set operation=financial_statement `
  --set statement=income_statement `
  --set frequency=annual `
  --set line_item=total_revenue `
  --set max_periods=4 `
  --pretty
```

Other variable combinations:

- snapshot: `symbol=NVS` and `operation=snapshot`
- Swiss-listed share: `symbol=NOVN.SW` and `operation=snapshot`
- allowlisted attribute: `symbol=NVS`, `operation=attribute`,
  `attribute=market_cap`
- quarterly balance sheet: `operation=financial_statement`,
  `statement=balance_sheet`, `frequency=quarterly`

## Supported launcher contract

The launcher exposes two reviewed profiles over the same adapter logic:

~~~text
queued_summary
  -> validate the intake and launcher contracts
  -> register the exact packaged key and version
  -> submit one bounded Assets run
  -> execute in local_worker or ECS
  -> keep queue and result projections value-light
  -> record the run UUID for observability

direct_result
  -> validate the intake and launcher contracts
  -> require the prewarmed dependency environment and outbound policy
  -> invoke the adapter once in the isolated child interpreter
  -> validate and size-bound the normalized response
  -> return the response directly to caller memory
  -> perform no Assets registration, queue submission, polling, or publication
~~~

The provider SDK remains inside YFinanceMarketDataAdapter. The launcher never
duplicates the call. Both profiles reuse the same bounded variables, dependency
lock, response schema, and egress admission. queued_summary is the default to
preserve current automation. direct_result must be explicitly allowed in the
launcher manifest and explicitly selected by the caller.

The canonical execution identity remains nusaibah.yfinance_market_data. Do not
invent or reuse an unrelated entity key.

## First-time readiness sequence

Run these commands after changing the adapter version, dependency lock, runtime
wheel, Python version, or worker platform.

1. Inspect the intake contract:

```powershell
E:\nusaibah_projects\demo_asset_project\.venv\Scripts\obs-adapter-intake-check.exe `
  --adapter-yaml E:\nusaibah_projects\demo_asset_project\adapter-intake-work\adapters\nusaibah\yfinance_market_data\adapter.yaml `
  --pretty
```

2. Inspect the launcher contract:

```powershell
E:\nusaibah_projects\demo_asset_project\.venv\Scripts\obs-asset-launch.exe doctor `
  --adapter-yaml E:\nusaibah_projects\demo_asset_project\adapter-intake-work\adapters\nusaibah\yfinance_market_data\adapter.yaml `
  --pretty
```

3. Prepare the exact dependency environment using the command shown earlier.
Expected status is `ready`.

4. Validate one launch without registration, queue submission, or provider
network access:

```powershell
E:\nusaibah_projects\demo_asset_project\.venv\Scripts\obs-asset-launch.exe run `
  --adapter-yaml E:\nusaibah_projects\demo_asset_project\adapter-intake-work\adapters\nusaibah\yfinance_market_data\adapter.yaml `
  --set symbol=NVS `
  --set operation=history `
  --set period=5d `
  --set interval=1d `
  --set max_rows=5 `
  --skip-publish `
  --pretty
```

Expected category is `governed_launch_inputs_ready` with
`network_calls_made=false`.

5. Run the live command from the Queue invocation section. The launcher performs
registration automatically, so a separate registration command is optional.

6. Prove direct result delivery with the command in Direct result invocation.
Expected evidence is status=success with outputs.market_data.data.records present and
no registration, run, or run_uuid fields.

## Successful responses

A successful queued_summary response has:

- top-level `status=completed`
- `registration.execution_enabled=true`
- `registration.registered[0].execution_admission=ready`
- `run.launch.run_uuid`
- `run.poll.final_status=completed`
- `run.values_included=true`
- the server-sanctioned result projection under `run.result` (full output values only when the server result policy admits them)

A successful direct_result response instead has response_version=1,
status=success, and the full normalized value under outputs.market_data. It has
no registration or run wrapper because no Assets API was called.

The run UUID is recorded by Assets and is visible in the DLM UI. Registration
is idempotent; repeating a launch updates the same launch entity and does not
create a new queue or require a worker restart.

## Lifecycle troubleshooting

Check the first failed stage instead of repeating every command:

| Stage | Ready evidence | Blocker meaning |
| --- | --- | --- |
| Intake | `adapter_intake_ready` | Local adapter files or declarations disagree |
| Launcher | `asset_launcher_doctor_ready` | Reviewed helper or launcher manifest is invalid |
| Dependency | `status=ready` | Exact isolated lock is unavailable |
| Registration | `execution_enabled=true` | Exact server package/surface/mode is not admitted |
| Launch | run UUID present | Assets rejected the request before queueing |
| Worker | terminal `completed` | Worker dependency, egress, provider, or adapter execution failed |
| Result | `run.result` present | Result endpoint or result sanitization failed |

`status=accepted` with `execution_enabled=false` is metadata registration
only; it is not execution readiness. Do not restart the queue to repair this.
Confirm that the Assets server has the same packaged key/version and that the
registration lifecycle fix is deployed.

## Durable workers and new assets

This launcher does not own worker lifecycle. A durable worker discovers reviewed
adapters beneath its own target root per request and uses no per-asset
`--allowed-adapter` argument. Adding another asset under the same reviewed root
requires intake, package admission, optional dependency prewarming, and
registration; it does not require changing the worker command or restarting the
worker or Assets queue.

Dependency environments are isolated per asset. The runtime authoring API loads
the global adapter registry lazily, so a yfinance child does not import SFDA,
LinkedIn, or any other adapter dependency.

A developer repository is one target scope, not a platform-wide root. Two
developers must have two independent target identities and repository roots;
ECS is another target pool. The current fixed local-worker URL supports one
target only. Do not combine developer repositories or replace that URL per run.
Use the server-side target registry/lease/routing contract documented in
`python_runtime/docs/durable_worker_targets.md`.

## PowerShell rules

The launcher uses individual `--set name=value` arguments, so no JSON escaping
is required. If a future asset accepts a URL reference, quote the entire
assignment because URLs can contain `&`:

```powershell
--reference "post_url=<QUOTED_HTTPS_URL_WITH_QUERY>"
```

Use `--reference` only when the launcher itself is authorized to call that
URL and the launcher manifest declares an allowlisted `url_reference`.
Use `--set source_url=...` only when a URL is ordinary data and the adapter
contract explicitly permits it. These are different contracts:

- URL as call target: reviewed launcher/runtime owns the network call and host policy.
- URL as data/reference: no automatic call; it is validated and transported as data.

## Reusable pattern for future assets

For another Python adapter, keep one adapter implementation and declare the
delivery profiles it truly supports:

1. Keep provider and normalization code inside the adapter or its admitted
   runtime client.
2. Add a reviewed helper and asset_launcher.v2 manifest beside the adapter.
3. Keep queued_summary as the default when observability is required.
4. Add direct_result only when a bounded synchronous response is appropriate.
   Declare profile_cli_arg, dependency_environment, and max_result_bytes.
5. In direct_result, call devtools.invoke_direct_adapter with the adapter
   instance. Do not call Assets registration, execute, status, trace, or result
   endpoints.
6. Require dependency prewarming and the outbound-policy gate for external SDKs.
7. Validate the standard adapter response and keep the direct result in caller
   memory. Do not create a temporary result file.
8. Unit-test that direct_result never calls registration or queue helpers, and
   that queued_summary still sends only bounded inputs and receives summaries.
9. Run intake check, launcher doctor, dependency preparation, skip-publish, a
   direct live proof, and a queued live proof before promotion.

A different Python asset can compose this adapter synchronously by importing
YFinanceMarketDataAdapter and devtools.invoke_direct_adapter, then passing
variables and a direct_result context. This nested call uses the target
adapter's own dependency fingerprint and returns the validated dictionary
directly; it does not create an Assets run.

Do not copy the historical fixture runner as a production launcher. Fixture
mode is useful for deterministic adapter tests, but it does not create a
recorded Assets run and must not perform a second live provider request.

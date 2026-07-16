# yfinance market-data asset

The registered `0.2.0` adapter accepts bounded variables directly. Its
injectable `YFinanceMarketDataClient` lazily imports `yfinance==1.5.1` only
inside an admitted per-dependency environment; no market-data fixture or MCP
HTTP connector is required.

The adapter performs no OBS, Core, storage, queue, publishing, or credential
work. It returns only the stable `market_data` output contract and converts
provider failures to value-safe error codes.

Asset identity: `nusaibah.yfinance_market_data:0.2.0`

## Supported operations

- `history`
- `snapshot`
- allowlisted `attribute`
- `financial_statement`

Financial statements support:

- `income_statement`
- `balance_sheet`
- `cash_flow`
- annual or quarterly frequency
- bounded periods and line items
- optional normalized line-item filtering, such as `total_revenue` or `operating_cash_flow`

Arbitrary `getattr()` is not supported. The unsafe snapshot field `timezone` is intentionally excluded from adapter output.

## Isolated local_worker preparation

Runtime `0.1.69` adds a generic dependency cache keyed by the exact lock,
runtime version, Python version, and platform. After the dependency and network
policy fields are explicitly approved, prewarm the environment once:

```powershell
E:\nusaibah_projects\demo_asset_project\.venv\Scripts\obs-asset-dependency-prepare.exe `
  --adapter-root E:\nusaibah_projects\demo_asset_project\adapter-intake-work `
  --adapter nusaibah.yfinance_market_data:0.2.0 `
  --runtime-artifact C:\xampp\htdocs\assets\python_runtime\dist\pi_obs_python_runtime-0.1.69-py3-none-any.whl `
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
  -PrimaryAdapter nusaibah.yfinance_market_data:0.2.0 `
  -DependencyManifest python_runtime\adapters\intake\nusaibah\yfinance_market_data\adapter.dependencies.json `
  -RuntimeWheel python_runtime\dist\pi_obs_python_runtime-0.1.69-py3-none-any.whl `
  -ImageTag yfinance-market-data-0.2.0 `
  -NoBuild
```

The bundle wheel pins the full declared dependency lock. ECS still requires the
packaged adapter registry entry and an enforced task egress policy.

## Production approval gate

`production_approval` remains `pending` for both the SDK dependency and outbound
network policy. This is intentional: technical isolation does not establish
Yahoo data-access permission or an enforced runtime egress allowlist. The
prewarm and ECS build gates fail closed until those approvals are changed by the
policy owner.

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

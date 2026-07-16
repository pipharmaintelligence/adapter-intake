# yfinance market-data asset

This folder has two separate lanes:

1. `dev_yfinance_tool.py` is a local developer tool. It uses `yfinance==1.5.1` and generates a safe fixture envelope.
2. `yfinance_market_data_adapter.py` is the registered adapter. It consumes `market_data_snapshot` plus safe `variables` and performs no provider, OBS, Core, storage, or publishing calls.

The manifest permits `local_worker` and `ecs`, but live remote execution still requires an approved runtime-owned market-data source to inject `market_data_snapshot`. The adapter dependency remains local-only because the registered adapter itself does not import `yfinance`.

Asset identity: `nusaibah.yfinance_market_data:0.1.0`

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

## Single-command local launcher

Use `run_yfinance_market_data.py` to provide ticker variables directly and receive the final adapter response in one command:

```powershell
python .\run_yfinance_market_data.py `
  --symbol NVS `
  --operation history `
  --period 5d `
  --interval 1d `
  --max-rows 5
```

The launcher performs only local developer orchestration:

1. validates safe CLI variables,
2. invokes `dev_yfinance_tool.py`,
3. writes the resolved fixture under ignored `.adapter-scratch/`,
4. invokes `obs-adapter-runner`, and
5. prints the final adapter response.

It does not publish outputs, register the asset, or provide remote `local_worker`/ECS provider authority.

## Financial statement examples

Annual Novartis revenue:

```powershell
python .\run_yfinance_market_data.py `
  --symbol NVS `
  --operation financial_statement `
  --statement income_statement `
  --frequency annual `
  --line-item total_revenue `
  --max-periods 4
```

Annual Novartis cash flow statement:

```powershell
python .\run_yfinance_market_data.py `
  --symbol NVS `
  --operation financial_statement `
  --statement cash_flow `
  --frequency annual `
  --max-periods 4 `
  --max-line-items 80
```

Quarterly balance sheet:

```powershell
python .\run_yfinance_market_data.py `
  --symbol NVS `
  --operation financial_statement `
  --statement balance_sheet `
  --frequency quarterly `
  --max-periods 4
```

Other examples:

```powershell
# Safe snapshot; timezone is excluded
python .\run_yfinance_market_data.py --symbol NVS --operation snapshot

# Swiss-listed Novartis share
python .\run_yfinance_market_data.py --symbol NOVN.SW --operation snapshot

# One allowlisted attribute
python .\run_yfinance_market_data.py --symbol NVS --operation attribute --attribute market_cap
```

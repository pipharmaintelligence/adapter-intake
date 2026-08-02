# YFinance Market Data Adapter 0.2.4

Asset identity: `nusaibah.yfinance_market_data:0.2.4`

This adapter performs bounded market-data and company-discovery calls through the admitted `yfinance==1.5.1` SDK dependency. It owns no credentials, URLs, storage placement, OBS/Core calls, queues, retries, publication, or cross-asset orchestration.

## Supported operations

- `history`
- `snapshot`
- `attribute`
- `financial_statement`
- `company_profile`
- `company_search`

`company_profile` returns an allowlisted profile for one resolved Yahoo symbol. `company_search` returns bounded Yahoo equity candidates in provider rank order for one company-name query.

The Yahoo adapter does **not** resolve SEC CIKs, score company-name similarity, select a canonical listing, classify SIC codes, or assert legal-entity equivalence. Those decisions belong in the deterministic `sec_yahoo_company_map` adapter.

## Company search request

```json
{
  "variables": {
    "operation": "company_search",
    "company_name": "Novartis AG",
    "max_results": 10,
    "timeout_seconds": 15
  }
}
```

Bounds:

- `company_name`: non-empty, normalized whitespace, at most 160 characters
- `max_results`: 1–25
- `timeout_seconds`: 1–60

Search output uses the existing `market_data` role:

```json
{
  "operation": "company_search",
  "data": {
    "candidates": [
      {
        "provider_rank": 1,
        "symbol": "NVS",
        "quote_type": "EQUITY",
        "short_name": "Novartis AG",
        "long_name": "Novartis AG",
        "display_name": null,
        "exchange_code": "NYQ",
        "exchange_name": "NYSE"
      }
    ]
  },
  "metadata": {
    "source_kind": "isolated_provider_sdk",
    "library_family": "yfinance",
    "query_kind": "company_name",
    "candidate_count": 1,
    "results_truncated": false
  }
}
```

No top-level `symbol` is emitted for `company_search`; the output contract therefore marks `symbol` optional. Existing symbol-based operations continue to emit it.

## Launcher examples

Direct result:

```powershell
obs-asset-launch run `
  --adapter-yaml .\adapter.yaml `
  --env-file E:\nusaibah_projects\demo_asset_project\.env `
  --execution-profile direct_result `
  --execution-substrate local_worker `
  --set operation=company_search `
  --set company_name="Novartis AG" `
  --set max_results=10 `
  --set timeout_seconds=15 `
  --pretty
```

## Validation

Run in the selected DataSpell interpreter after installing the OBS runtime package:

```powershell
python -m pytest -q
python -m compileall -q .
```

Before promotion, run intake, diagnose, dependency, fixture, direct-result, and governed local-worker checks for the exact `0.2.4` identity. A version change requires a new catalog entry and promotion; do not overwrite a promoted `0.2.3` entry.

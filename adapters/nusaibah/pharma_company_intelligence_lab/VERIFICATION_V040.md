# Version 0.1.40 — evidence and release boundary

## Objective

Verify the proposed repair for grounded discovery, useful company profiles, claim-local critics, actionable methodology, bounded reflection, and canonical Skill publication. **Do not equate these offline results with live release closure.**

## System Context

Base: adapter-intake `0960aba` (main, fetched before review). Asset candidate: `nusaibah.pharma_company_intelligence_lab:0.1.40`. Researcher and critic contracts: `1.0.12`. Historical versioned implementation bytes are unchanged. Runtime qualification uses the existing E environment's installed `pi-obs-python-runtime`; no install, wheel build, or package version change was performed.

## Approach

The deterministic fixtures exercise complete orchestration with the real pinned exact-span toolkit and synthetic Agent/Skill transports. Separate tests use the actual installed SDK for native citation projection, text-kind JSON parsing and first-package Skill document initialization. No network/provider/storage mutation is involved.

## Changes Made

| Acceptance area | Offline evidence | Remaining qualification |
|---|---|---|
| A01–A06: grounded discovery and evidence boundaries | Search-enabled contracts; failed HTTP plus native citations; text-kind wrapped JSON retaining provider metadata; rejection of a model-only URL; provider support-to-chunk mapping without invented quotes | Real provider search/grounding and business content inspection after promotion |
| A07–A12: constructive critics and methodology | Negative coverage preserves supported claims; all-empty research still saves useful critic advice; subsequent call consumes scoped advice; resolved guidance stops recurring while history stays | Real critic quality and persisted guidance inspection |
| A13–A16: coherent partial output and Annex | Actual publication candidate contains supported profile sections, references and the compact review table; malformed/unavailable synthesis does not erase reviewed facts | Inspect the live published Markdown, not merely run status |
| A17–A22: recovery and Skill boundaries | One backup per failing critic call; formatting repair cannot alter new decisions/advice; concurrent resource changes stop overwrite; missing memory/methodology initialize through real SDK helpers; oversized existing memory is preserved | Live Core receipt/readback, existing ZIP-resource preservation, storage authorization/admission |
| A23–A27: compatibility, bounds and operational truth | Immutable historical helpers; complete suite and promotion-shape checks; finite call/concurrency/input budgets; explicit incomplete states and no invented upload | Official materialization/package/catalog CI and artifact provenance; actual usage and output-size observations |
| A28–A30: optional reflection | One-pass default; two passes consume the prior in-memory result and advice without intermediate writes; three-pass request shares a hard budget and preserves earlier facts when exhausted | Provider timing and business benefit of reflection, only after a separately authorized run |

These are evidence groups, not a declaration that every end-to-end criterion is closed. The exact A01–A30 definitions in [acceptance criteria](ACCEPTANCE_V040.md) remain controlling.

## Modularity Impact

Only adapter-intake business files change. No Assets/Core source, server configuration, E runner configuration, worker restart, registration or deployment is part of this PR. Existing production 0.1.39 remains in service until an approved official promotion.

## Validation

Local results (2026-10-14): promotion-shape suite **2 passed**; full pharma suite **566 tests, OK, 14 expected skips**; current real-SDK qualification **17 passed**; isolated packaged import **passed** using only the **150 declared Python files**, resolving exactly version **0.1.40** on runtime **0.1.106**. No provider call was made.

Commands from the intake root:

```powershell
$Python = 'E:\nusaibah_projects\demo_asset_project\.venv\Scripts\python.exe'
$env:PYTHONDONTWRITEBYTECODE = '1'
$env:PYTHONUTF8 = '1'
& $Python -B -m unittest discover -s tests -p test_adapter_intake_contract.py -v

# The same dependency-free suite used by intake CI.
$env:PYTHONPATH = 'adapters/nusaibah/pharma_company_intelligence_lab/tests/stubs'
& $Python -B -m unittest discover -s adapters/nusaibah/pharma_company_intelligence_lab/tests -p 'test_*.py' -q

# Qualification against the installed SDK, without provider calls.
Remove-Item Env:PYTHONPATH -ErrorAction SilentlyContinue
& $Python -B -m unittest discover -s adapters/nusaibah/pharma_company_intelligence_lab/tests -p test_grounded_profile_v0_1_40.py -v
```

Native-citation and SDK-initialization tests intentionally skip under the minimal CI stubs. They must pass in the real-runtime qualification command; a skipped stub test does not prove those capabilities.

## Risks / Open Questions

- Merge, official promotion, Agent provisioning, runtime installation, and paid live verification are **pending by instruction**.
- Offline fixtures cannot prove arbitrary-company factual accuracy, actual search usage, provider compatibility in a deployed environment, or completion of every section within 30 minutes.
- The preserved authority/concurrency checks may legitimately stop an unsafe write. Availability and quality problems are scoped; they are never converted into fabricated evidence or successful upload receipts.
- Real profile quality must be judged by relevant supported content and disclosed gaps, not by a minimum word/fact count.

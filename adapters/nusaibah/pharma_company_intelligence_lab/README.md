# Nusaibah Pharma Company Intelligence Lab

Canonical adapter-intake source for `nusaibah.pharma_company_intelligence_lab`.

## Version policy

`0.1.3` is the current immutable candidate. It corrects the governed company-input contract after live `0.1.2` proof showed that direct caller-supplied `companies` data could bypass the intended Assets/DLM binding path.

Create a new asset version whenever adapter code, manifest metadata, reviewed helpers, dependency contract, or portable Skill bytes change. Environment-only repairs such as publishing an unchanged immutable Skill do not require an asset-version bump.

## Batch contract

The target launch variable is a bounded `company_ids` array such as `[13, 59]`. `companies` is binding-owned and `variables` is direct. The governed company source is `lake_id=test_database_lake`, `node_key=companies`; its primary-key column is `id` and its company-name column is `company`. Assets/Core must resolve the governed `companies` input before Python starts. The adapter normalizes `id -> company_id` and `company -> company_name`, validates exact requested/resolved ID parity, and processes each company context independently. Python does not query DLM/Core or the database directly.

## Format ownership

`dossier_contract.py` owns exact section IDs, subsection IDs, titles, and order. Agents return machine IDs and content only. Titles and hierarchy are rendered deterministically by the adapter so report structure cannot drift by provider, company, or run.

## Promotion ownership

This adapter-intake folder is the reviewed source package. Published Assets materialization must be produced through the pinned adapter-intake promotion workflow rather than by hand-editing the packaged Assets directory.

Development progress and release evidence are tracked in Linear PI-1951 and in the development-only `tests/DEVELOPMENT_CHECKLIST.md`; that checklist is intentionally excluded from promoted runtime bytes.
## DLM UI binding readiness boundary

The manifest intentionally declares `companies.source=binding` so Assets projects that role to the DLM UI Input Binding workflow, while `variables.source=direct` keeps launch variables out of the binding picker.

Role visibility is not the same as a ready database selector. The current database node uses ordinary schema column `id`; it must not be mislabeled as a partition field. The governed binding/runtime layer must support the row/data mapping `id <- company_ids` before live variables-only execution can be considered proven.

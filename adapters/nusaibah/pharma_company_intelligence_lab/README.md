# Nusaibah Pharma Company Intelligence Lab

Canonical adapter-intake source for `nusaibah.pharma_company_intelligence_lab`.

## Version policy

`0.1.0` remains a mutable development candidate in adapter-intake until every pre-publication release gate is green. Do not create the final Assets promotion PR merely because the foundation package validates.

After `0.1.0` is merged/deployed as an immutable packaged identity, a later failure requires `0.1.1` only when the fix changes adapter code, manifest, reviewed helpers, dependency contract, or portable Skill bytes. Environment/binding/admission/provider fixes that do not change package bytes do not require an adapter version bump.

## Batch contract

The target launch variable is a bounded `company_ids` array such as `[13, 59]`. Assets/Core resolves the governed `companies` input before Python starts. The adapter validates exact requested/resolved ID parity and processes each company context independently.

## Format ownership

`dossier_contract.py` owns exact section IDs, subsection IDs, titles, and order. Agents return machine IDs and content only. Titles and hierarchy are rendered deterministically by the adapter so report structure cannot drift by provider, company, or run.

## Promotion ownership

This adapter-intake folder is the reviewed source package. Published Assets materialization must be produced through the pinned adapter-intake promotion workflow rather than by hand-editing the packaged Assets directory.

Development progress and release evidence are tracked in Linear PI-1951 and in the development-only `tests/DEVELOPMENT_CHECKLIST.md`; that checklist is intentionally excluded from promoted runtime bytes.

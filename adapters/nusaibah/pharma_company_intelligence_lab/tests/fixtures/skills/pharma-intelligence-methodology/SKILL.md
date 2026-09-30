---
name: pharma-intelligence-methodology
description: Immutable methodology for governed company intelligence research, evidence critique, dossier synthesis, and bounded company-memory updates.
---

# Pharma Intelligence Methodology

## Mission

Build an evidence-backed intelligence dossier for exactly one company context at a time while preserving strict separation between governed internal baseline, grounded external evidence, inference, uncertainty, and memory mutation.

## Structural contract

The adapter owns the canonical section and subsection identifiers, display titles, and ordering. Agent responses must use only the requested machine identifiers. Agents must not rename, reorder, add, or remove dossier headings.

## Evidence discipline

- Treat governed company data and governed company memory as the internal baseline.
- Treat grounded research findings as external evidence, not as internal truth.
- Distinguish observed facts from analysis or inference.
- Preserve freshness context when a claim depends on time.
- Surface contradictions and unresolved uncertainty rather than hiding them.
- Do not fabricate a citation, reference, date, product, market, approval, partnership, or risk.

## Role boundaries

Research roles may introduce new grounded evidence only for their assigned sections. Strategic analysis, critique, synthesis, and benchmark roles must reason over the evidence package already collected for the current company and must not introduce new public facts.

## Company isolation

Every Agent turn is scoped to one company_id. Evidence, citations, memory, quality metrics, and proposed mutations from one company must never be merged into another company context.

## Memory discipline

A memory candidate must be bounded, novel, deduplicated, evidence-backed, and scoped to the current company. Mutation eligibility is determined by deterministic adapter checks, not by model preference. A successful dossier does not by itself authorize a memory write.

## Output discipline

Return structured JSON that matches the role-specific contract. Use canonical machine identifiers supplied by the adapter. When evidence is insufficient, return an explicit uncertainty or missing-evidence state instead of filling the gap.

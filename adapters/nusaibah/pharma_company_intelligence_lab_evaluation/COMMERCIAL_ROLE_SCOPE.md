# Commercial role ownership: proposal and candidate repair

## Observed quality issue

The first independently reviewed 0.2.2 development case, `company-small-identity-001`, recovered its one expected headquarters finding. A second accepted commercial finding repeated the headquarters claim using the same `company:1` span. The supplied-source evidence was valid; the problem was semantic role overlap. The existing question admits geography without requiring a commercial activity. Finding identities include role and requirement, so distinct IDs do not establish distinct claims.

## Proposed boundary

| Requirement | Owns | Does not establish |
| --- | --- | --- |
| `company_identity` | Legal name, headquarters, registered address, incorporation and company-profile identity | Customer markets, sales presence or distribution solely from an address |
| `commercial_signals` | Explicit sales/customer markets, distribution territories, market access, revenue, commercial launches and commercialization/licensing partnerships | Headquarters, registered addresses or identity-only geography |

A headquarters-only or registered-address-only source must yield `no_evidence` with an empty findings list for `commercial_signals`. Geography remains commercial when the source explicitly ties it to sales, customers, distribution or another admitted commercial activity. A location can appear in both lanes when it supports genuinely different claims; a commercial agreement does not cease being commercial because its quote also mentions headquarters.

The exact narrowed questions and requirement scopes are versioned in [the offline contract proposal](tests/fixtures/commercial_role_scope.v1.json). They carry `status=offline_proposal`. They are not an admitted adapter or Agent contract.

## Deterministic regression evidence

Run from adapter-intake using the existing E: Python environment:

```powershell
$ProjectRoot = 'E:\nusaibah_projects\demo_asset_project'
$IntakeRoot = "$ProjectRoot\adapter-intake-work"
& "$ProjectRoot\.venv\Scripts\python.exe" -B -m unittest discover `
  -s "$IntakeRoot\adapters\nusaibah\pharma_company_intelligence_lab_evaluation\tests" `
  -p 'test_commercial_role_scope.py' `
  -v
```

The tests exercise the actual quote orchestration and deterministic toolkit with canned specialist/verifier responses. They cover headquarters-only and registered-address-only abstention, explicit sales geography, and distinct identity/distribution claims sharing one exact quote. They also reproduce the current two-role duplicate and demonstrate that a prompt proposal alone does not deterministically reject a deliberately noncompliant commercial response. The expected/scripted responses remain outside source inputs and Agent packets. These are contract/protocol regressions, not measurements of model compliance or independent factual quality.

The proposal has a separate test-side methodology digest. Production 0.2.0/0.2.1/0.2.2 source modules, Agent declarations, stored inputs, retained results, review receipts and frozen suite truth remain unchanged. The historical 0.2.2 methodology digest is asserted explicitly. Existing three-way parallelism, sequential verification, one toolkit call per chunk, finite call ceilings, deadline and zero repair loops remain intact.

## Candidate 0.2.3 source implementation

The narrowed questions and scopes are now implemented in `supplied_source_scoped_review.py`, signed in `supplied_source_methodology.v3`. The new candidate uses the reusable finite `quote_review_orchestration.py` profile and the existing exact-span toolkit. It passes requirement scopes into both specialist proposals and existing local/global verifier contracts. The validator retains closed schemas and bound verdicts; it does not infer role ownership from substrings or citation equality.

The original proposal tests remain, and candidate-specific tests exercise the actual configured source helper: identity-only abstention, genuine market geography, same-span distinct claims, withholding a misrouted claim when the bound semantic verifier rejects it, historical orchestration parity, concurrent old/new profile isolation and finite controls. A deliberately noncompliant supported verdict still demonstrates the semantic proof limit. These are scripted protocol tests; the next admitted live result needs independent review.

The new wrapper/manifest/Agent definitions and promotion helper declarations are confined to adapter-intake. All historical manifest version definitions and source modules remain unchanged. The offline evaluator/projector accept explicit 0.2.3 selection with the original input bytes and a separate candidate/methodology binding. See [official workflow promotion](DEVELOPER_GUIDE.md#official-workflow-promotion); no runtime package upgrade or manual wheel update is part of this repair.

## Repair recommendation and decision boundary

Prefer the narrowed role contract as the first repair: it addresses the generation boundary and retains genuine commercial geography. Any runtime adoption must use a new versioned methodology and candidate/Agent contract where its definition changes, followed by the existing official promotion and admission path. Do not silently alter 0.2.2 or manually update a wheel.

Do not deduplicate by locator, offsets or quote alone: the shared-span regression supports two different claims. Do not reject every commercial statement containing a headquarters keyword: a supported distribution/licensing claim can legitimately include that context. Exact provenance and structural validation do not establish semantic role ownership.

A stronger acceptance boundary would require reviewed structured fact types or a semantic role-scope verdict with bound claim identity and explicit redundant/out-of-scope accounting. A deterministic validator can check a supplied label's schema and ownership; it cannot establish that a free-text claim was correctly labeled. That would be a separately reviewed schema/verification change, not a substring filter or silent deletion of a supported claim.

This PR includes the selected prompt-contract repair as source candidate 0.2.3. It does not claim deployed or measured semantic success, authorize another live case, change evaluation thresholds, or complete WP1. Review/merge the source, use official workflow promotion, and establish exact delivery/admission before considering another live case.

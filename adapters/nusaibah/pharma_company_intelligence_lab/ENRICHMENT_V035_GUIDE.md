# Objective

Align paragraph enrichment with the pinned reusable exact-span operation and retain unavailable chunks without extra provider retries.

# System Context

0.1.34 run eabdb19d-a04c-4108-928a-869d5f7618c2 stopped at a callable boundary. A provider-free probe against real company-14 memory reproduces review_tool_source_size_limit: the admitted memory unit is 7193 characters, while toolkit 0.1.1 permits 6000 per unit and 24000 total. Sixteen Agent receipts completed; one portfolio member refresh failed separately. Core Skill packages/resources remain unchanged.

# Approach

Pin reusable toolkit 0.1.2. Its exact-span operation has finite 60000-character unit, 120000-character total and 262144-byte request limits; other operations and old versions keep their limits. Premeasure the actual verification request. Reuse exact root locators, snapshots, offsets, uniqueness and entity checks; never fabricate spans or cut source characters.

# Changes Made

Explicit provider-member refresh unavailability and effect-free exact-span invocation unavailability become unresolved affected chunks, without new retries or paid backup calls for infrastructure failure. Authentication/authority/mismatch errors and malformed or forged returned toolkit evidence still propagate. Existing JSON backup behavior remains one per original.

# Modularity Impact

The bounded size extension lives in the reusable toolkit, not a copied verification engine. No Core/generic runtime/storage/policy change, and runtime stays 0.1.105. Preserve prior published code. Promote toolkit before its consumer, deliver one verified official artifact after both merges.

# Validation

Test real 7193 and 60000-character inputs, boundary rejection, Unicode byte accounting, native callable bridge and isolated closure. Test affected-chunk availability handling, no added retries, siblings, negative critics and authority rejection. No further provider run until these pass and the exact pins are admitted.

# Risks / Open Questions

Unavailable chunks and bounded source admission can leave coverage incomplete. Only independently validated evidence may publish. Actual Core receipts/readback/history remain required; no-change is not a new ZIP. Unknown authority failures must not be turned into successful claims.

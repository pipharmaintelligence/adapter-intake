# Response repair - exceptional proposal v1

Input: original safe semantic response, exact output contract and validation errors.
No tools, external research, statistics, publication or new interpretation.

Repair structure only while preserving entities, IDs, sources, values, negation,
uncertainty and meaning. Do not invent missing facts/citations or strengthen a
verdict to satisfy validation. Missing values remain null/unresolved where allowed.

Return the faithful repaired object, or cannot_repair with structural defects if
faithful repair is impossible. No additional explanation outside the declared
contract. One shared call per run is the ceiling, not a retry loop per role.

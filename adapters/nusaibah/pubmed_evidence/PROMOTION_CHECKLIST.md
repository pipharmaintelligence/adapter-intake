# PubMed Evidence 0.1.0  -  release and promotion checklist

**Source stage:** new adapter-intake package. No source IDs, admission,
registered publication, release or live proof are presumed.

| Gate | Initial state | Acceptance evidence |
|---|---|---|
| P0 code and fixtures | Local synthetic tests required | All provider-free operation and rejection tests passing on Python 3.10+ |
| P0 intake descriptor | New | Strict declared-file list, matching key/version/adapter module |
| P0 forbidden-content scan | New | No literal request targets in declared files; no disallowed sensitive code words, assignment patterns or transport escapes |
| P1 immutable source | Not created yet | Exact remote full intake SHA and CI status |
| P2 promotion plan | Not run | Official Assets dry-run/planner ready without mutations |
| P3 cumulative materialization | Not run | Existing Assets versions coexisting, no shared-file conflict |
| P4 generated manifests/catalog | Not run | Same source SHA in package metadata and build plan |
| P5 built wheel/sdist | Not run | Both archive scanner and PHP source boundary green |
| P5 package & OS CI | Not run | Dotted import, full PHP integration, Windows and sensitive-artifact gate |
| P6 exact-head PR | Not created yet | Diff limited to new asset and scoped intake CI; all required checks green |
| P7 merge | Not done | Verified merge SHA and no unexpected retirement |
| P8 local_worker | Not deployed | Running exact wheel/catalog/worker digest and signed proof |
| P8 ECS | Not deployed | Built, pushed immutable image digest and deployed task definition |
| Core sources and admission | Unknown | Each of six roles approved and ready for exact client/substrate |
| Primitive live proof | Not run | Safe counts/shape per source role, including rejected/failure cases |
| Clinical composition | Not run | Fresh combined admitted run in later clinical version |
| Public MCP tools | Templates only | Separate reviewed publication and remote protocol proof |

## Two independent package scanners

1. Assets built archives are inspected using the Python archive scanner.
2. The Assets PHP package-boundary suite examines raw Python source
   literals and identifiers; even defensive expressions can be rejected.

Run **both**, rather than assuming one passing implies the other. The
repository-wide workflow also has a separate intake YAML and declared-file
scanner. Do not exempt this asset path or disable tests to obtain green CI.

Only run promotion using the immutable intake SHA after exact-head intake CI
passes. The Assets promotion workflow conditionally builds the ECS image
locally; image creation is **not** ECR publication or task deployment.
The adapter is neither live-ready nor consumer-ready until those separately
observed deployment and admission gates pass.

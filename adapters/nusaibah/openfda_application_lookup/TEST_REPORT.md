# Test Report

Validation performed offline against the packaged source.

- Unit/package contract tests: Ran 19 tests in 0.001s
- Result: OK
- Python compilation: PASS
- Provider HTTP call: NOT RUN
- OBS/Core recorded run: NOT RUN
- Credential material inspected: NO
- Binding configuration: NONE
- Output publication configuration: NONE

The live acceptance step remains intentionally separate because it must use the
existing governed Runtime Source and trusted local worker rather than a direct
provider call from the adapter test suite.

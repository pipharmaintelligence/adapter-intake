# Synthetic consumer developer guide

From the repository root, run `python -m unittest discover -s tests -p test_structured_review_toolkit.py -v` with the development runtime installed. Then run `python tests/prove_review_toolkit_worker.py` to prove official materialization, isolated parent/child execution and response signatures for both consumers without any provider calls.

The source fixture builder in `tests/test_structured_review_toolkit.py` is development-only and is excluded from the promoted runtime. Expected semantic states are fixture assertions; do not insert adjudication truth into future Agent input.

The consumer pins the toolkit version, validates its synthetic entity prefix and supplies its own methodology requirement. Domain input and methodology compatibility require review when adding another consumer. Use [the shared developer guide](../structured_review_toolkit/DEVELOPER_GUIDE.md) for schemas, counts, invocation limitations and official promotion order.
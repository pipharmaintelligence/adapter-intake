"""One public-reference allowance for the whole invocation, including reflection."""
from threading import Lock
from devtools.public_web_runtime import PublicWebRuntimeError

MAX_REFERENCE_READS = 20


class ReferenceBudgetInputs(dict):
    def __init__(self, inputs):
        super().__init__(inputs)
        self._inputs = inputs
        self._reference_lock = Lock()
        self._reference_reads = 0

    def __getattr__(self, name):
        return getattr(self._inputs, name)

    def __getitem__(self, key):
        return self._inputs[key]

    def get(self, key, default=None):
        return self._inputs.get(key, default)

    @property
    def remaining_reference_reads(self):
        with self._reference_lock:
            return MAX_REFERENCE_READS - self._reference_reads

    def open_reference(self, target, *, mode='auto'):
        with self._reference_lock:
            if self._reference_reads >= MAX_REFERENCE_READS:
                raise PublicWebRuntimeError('public_web_reference_budget_exhausted')
            self._reference_reads += 1
        return self._inputs.open_reference(target, mode=mode)

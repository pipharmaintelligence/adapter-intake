"""Error-only SDK surface for provider-free intake CI; no fake transport."""

class RuntimeAgentInvocationError(RuntimeError):
    def __init__(self, reason, *, cause_code=None, proof_failure_detail=None):
        super().__init__(reason)
        self.cause_code = cause_code
        self.proof_failure_detail = proof_failure_detail

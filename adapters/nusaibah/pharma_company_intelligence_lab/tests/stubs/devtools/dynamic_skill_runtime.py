class DynamicSkillRuntimeError(RuntimeError):
    """Minimal runtime-compatible error carrying a safe code."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)

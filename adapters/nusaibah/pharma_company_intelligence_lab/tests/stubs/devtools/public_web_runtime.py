"""Error-only compatibility stub; never exposes a fake transport."""
class PublicWebRuntimeError(RuntimeError):
    def __init__(self,code):
        self.code=code
        super().__init__(code)

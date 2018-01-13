from typing import Optional


class CompileException(Exception):

    def __init__(self, reason: str, trace: Optional[str] = None):
        super().__init__(reason, trace)
        self.reason = reason
        self.trace = trace

    def __str__(self):
        return f"{self.reason}\n{self.trace}"




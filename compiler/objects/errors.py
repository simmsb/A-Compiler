from typing import Optional


class CompileException(Exception):

    def __init__(self, *reasons: str, trace: Optional[str] = None):
        super().__init__(*reasons, trace)
        self.reason = "\n".join(reasons)
        self.trace = trace

    def __str__(self):
        return f"{self.reason}\n{self.trace}"




from typing import Optional


class CompileException(Exception):
    """Raised when an error is caused by the source code the compiler is trying to compile."""

    def __init__(self, *reasons: str, trace: Optional[str] = None):
        super().__init__(*reasons, trace)
        self.reason = "\n".join(reasons)
        self.trace = trace

    def __str__(self):
        return f"{self.reason}\n{self.trace}"


class InternalCompileException(Exception):
    """Raised when an internal compiler error occurs, should not happen."""
    pass

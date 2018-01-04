def emptyfn(body: str) -> str:
    """Wrap body inside of an empty function"""
    return f"fn test() -> u1 {{{body}}}"

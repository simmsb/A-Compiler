def emptyfn(body: str, return_type: str="u1") -> str:
    """Wrap body inside of an empty function"""
    return f"fn test() -> {return_type} {{{body}}}"

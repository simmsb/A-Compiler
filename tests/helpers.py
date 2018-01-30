from typing import Callable, TypeVar


def emptyfn(body: str, return_type: str="u1") -> str:
    """Wrap body inside of an empty function"""
    return f"fn test() -> {return_type} {{{body}}}"


RT = TypeVar('RT')


def for_feature(**features: str) -> Callable[[Callable[..., RT]], Callable[..., RT]]:
    features = ((f"feature-{k}", v) for k, v in features.items())

    def deco(f: Callable[..., RT]) -> Callable[..., RT]:
        f._features = features
        return f
    return deco

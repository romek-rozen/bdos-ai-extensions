"""Pairwise similarity backends: lexical (stdlib) and fuzzy (rapidfuzz)."""
from difflib import SequenceMatcher
from .normalize import normalize, tokens

def token_set(text: str) -> frozenset:
    return frozenset(tokens(text))

def jaccard(a: str, b: str) -> float:
    sa, sb = token_set(a), token_set(b)
    if not sa and not sb:
        return 1.0
    if not sa or not sb:
        return 0.0
    return len(sa & sb) / len(sa | sb)

def lexical_similarity(a: str, b: str) -> float:
    """Blend token-set Jaccard with character-level ratio; return the stronger signal."""
    ratio = SequenceMatcher(None, normalize(a), normalize(b)).ratio()
    return max(jaccard(a, b), ratio)

def has_rapidfuzz() -> bool:
    try:
        import rapidfuzz  # noqa: F401
        return True
    except ImportError:
        return False

def fuzzy_similarity(a: str, b: str) -> float:
    try:
        from rapidfuzz.fuzz import token_sort_ratio
    except ImportError as e:
        raise RuntimeError("rapidfuzz not installed; run install() or use method='lexical'") from e
    return token_sort_ratio(normalize(a), normalize(b)) / 100.0

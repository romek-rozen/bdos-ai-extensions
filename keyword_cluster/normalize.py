"""Language-agnostic normalization + tokenization (pure stdlib)."""
import re
import unicodedata

_TOKEN_RE = re.compile(r"[^\W_]+", re.UNICODE)
# Match the base letter/digit in a Unicode character name, e.g.
# "LATIN SMALL LETTER L WITH STROKE" -> "L". Language-agnostic: relies only on
# the generic Unicode Character Database, no per-language word lists.
_BASE_RE = re.compile(r"^LATIN (?:SMALL|CAPITAL) LETTER ([A-Z])(?: WITH .+)?$")


def _strip_to_base(char: str) -> str:
    """Reduce a Latin letter with a non-decomposable modifier (e.g. ł, ø, đ)
    to its base letter using its Unicode name. Non-Latin characters and plain
    letters are returned unchanged."""
    if char.isascii():
        return char
    match = _BASE_RE.match(unicodedata.name(char, ""))
    if match:
        return match.group(1).lower()
    return char


def normalize(text: str) -> str:
    """Lowercase, strip diacritics (NFKD + drop combining marks), reduce
    non-decomposable Latin letters to their base, and collapse whitespace."""
    decomposed = unicodedata.normalize("NFKD", text.lower())
    stripped = "".join(c for c in decomposed if not unicodedata.combining(c))
    based = "".join(_strip_to_base(c) for c in stripped)
    return " ".join(based.split())


def tokens(text: str) -> list[str]:
    """Normalized alphanumeric tokens (Unicode word chars, no punctuation)."""
    return _TOKEN_RE.findall(normalize(text))

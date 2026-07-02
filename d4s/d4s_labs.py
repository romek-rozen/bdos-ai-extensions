"""
d4s_labs.py — DataForSEO Labs wrappers (SEO/intent context around keywords).

Keyword ideas and suggestions, bulk keyword difficulty, and search intent. Useful
alongside the Google Ads data for prioritising and grouping keywords.
"""

from ._util import geo, get_client

_KEYWORD_IDEAS = "/v3/dataforseo_labs/google/keyword_ideas/live"
_KEYWORD_SUGGESTIONS = "/v3/dataforseo_labs/google/keyword_suggestions/live"
_KEYWORD_DIFFICULTY = "/v3/dataforseo_labs/google/bulk_keyword_difficulty/live"
_SEARCH_INTENT = "/v3/dataforseo_labs/google/search_intent/live"


def keyword_ideas(keywords, location=None, language=None, client=None):
    """Keyword ideas from a set of seed keywords."""
    task = geo({"keywords": list(keywords)}, location, language)
    return get_client(client).call(_KEYWORD_IDEAS, [task])


def keyword_suggestions(keyword, location=None, language=None, client=None):
    """Long-tail suggestions that contain a single seed keyword."""
    task = geo({"keyword": keyword}, location, language)
    return get_client(client).call(_KEYWORD_SUGGESTIONS, [task])


def keyword_difficulty(keywords, location=None, language=None, client=None):
    """Bulk keyword difficulty (0-100) for keywords."""
    task = geo({"keywords": list(keywords)}, location, language)
    return get_client(client).call(_KEYWORD_DIFFICULTY, [task])


def search_intent(keywords, language=None, client=None):
    """Classify keywords by search intent (informational/navigational/...)."""
    task = geo({"keywords": list(keywords)}, None, language)
    return get_client(client).call(_SEARCH_INTENT, [task])

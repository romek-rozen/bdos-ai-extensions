"""
d4s_serp.py — SERP wrappers (competitor and demand context).

Live Google organic SERP (advanced), SERP-based competitor discovery, and Google
autocomplete suggestions for cheap keyword expansion.
"""

from ._util import geo, get_client

_ORGANIC = "/v3/serp/google/organic/live/advanced"
_SERP_COMPETITORS = "/v3/dataforseo_labs/google/serp_competitors/live"
_AUTOCOMPLETE = "/v3/serp/google/autocomplete/live/advanced"


def serp(keyword, location=None, language=None, client=None):
    """Live organic SERP (advanced) for a single keyword."""
    task = geo({"keyword": keyword}, location, language)
    return get_client(client).call(_ORGANIC, [task])


def serp_competitors(keywords, location=None, language=None, client=None):
    """Domains competing across the SERPs of the given keywords."""
    task = geo({"keywords": list(keywords)}, location, language)
    return get_client(client).call(_SERP_COMPETITORS, [task])


def autocomplete(keyword, location=None, language=None, client=None):
    """Google autocomplete suggestions for a keyword."""
    task = geo({"keyword": keyword}, location, language)
    return get_client(client).call(_AUTOCOMPLETE, [task])

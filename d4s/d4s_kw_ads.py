"""
d4s_kw_ads.py — Keywords Data / Google Ads wrappers (the Keyword-Planner data).

These are the highest-value endpoints for Google Ads work: search volume + CPC +
competition, keyword expansion from a site or seed keywords, ad-traffic
estimation at a bid, and Google Trends demand seasonality. Each returns an
``ok``-dict; pass ``client=`` to reuse a configured Client (else one is built
from env credentials).
"""

from ._util import geo, get_client

_SEARCH_VOLUME = "/v3/keywords_data/google_ads/search_volume/live"
_KEYWORDS_FOR_SITE = "/v3/keywords_data/google_ads/keywords_for_site/live"
_KEYWORDS_FOR_KEYWORDS = "/v3/keywords_data/google_ads/keywords_for_keywords/live"
_AD_TRAFFIC = "/v3/keywords_data/google_ads/ad_traffic_by_keywords/live"
_TRENDS = "/v3/keywords_data/google_trends/explore/live"


def search_volume(keywords, location=None, language=None, client=None):
    """Search volume, CPC and competition for keywords."""
    task = geo({"keywords": list(keywords)}, location, language)
    return get_client(client).call(_SEARCH_VOLUME, [task])


def keywords_for_site(target, location=None, language=None, client=None):
    """Keyword ideas relevant to a target URL/domain."""
    task = geo({"target": target}, location, language)
    return get_client(client).call(_KEYWORDS_FOR_SITE, [task])


def keywords_for_keywords(keywords, location=None, language=None, client=None):
    """Related keyword recommendations expanded from seed keywords."""
    task = geo({"keywords": list(keywords)}, location, language)
    return get_client(client).call(_KEYWORDS_FOR_KEYWORDS, [task])


def ad_traffic_by_keywords(keywords, bid, match="broad", location=None, language=None, client=None):
    """Estimate impressions/clicks/cost for keywords at a given bid and match type."""
    task = geo({"keywords": list(keywords), "bid": bid, "match": match}, location, language)
    return get_client(client).call(_AD_TRAFFIC, [task])


def google_trends(keywords, location=None, language=None, client=None):
    """Google Trends demand seasonality over time for keywords."""
    task = geo({"keywords": list(keywords)}, location, language)
    return get_client(client).call(_TRENDS, [task])

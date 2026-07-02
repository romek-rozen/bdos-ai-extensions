"""
d4s — thin, self-contained DataForSEO REST client for BDOS.

A pure standard-library HTTP client (no pip deps, independent of the dfs-mcp MCP
server) focused on Google Ads / SEO workflows: keyword volume + CPC, keyword
expansion, ad-traffic estimation, SERP and competitor context, Google Ads
Transparency, and Google Shopping. Read/analyze only — never mutates a Google
Ads account.

Credentials come from the environment (matching the dfs-mcp names):
    DATAFORSEO_USERNAME  (alias: DATAFORSEO_LOGIN)
    DATAFORSEO_PASSWORD

Get a DataForSEO account: https://skq.pl/data4seo  (affiliate link)

Public API (import path inside BDOS):
    from my.extensions.d4s import Client, search_volume, keyword_ideas, serp

    c = Client()                       # reads env credentials
    r = c.call("/v3/dataforseo_labs/google/keyword_ideas/live", [{...}])

    # or convenience wrappers (each accepts an optional client=):
    r = search_volume(["buty trekkingowe"], location="Poland", language="Polish")
    for row in r["result"]:
        print(row["keyword"], row["search_volume"], row["cpc"])
"""

from . import d4s_ads_intel, d4s_kw_ads, d4s_labs, d4s_merchant, d4s_meta, d4s_serp
from .d4s_ads_intel import ads_advertisers, ads_search
from .d4s_client import Client
from .d4s_kw_ads import (
    ad_traffic_by_keywords,
    google_trends,
    keywords_for_keywords,
    keywords_for_site,
    search_volume,
)
from .d4s_labs import keyword_difficulty, keyword_ideas, keyword_suggestions, search_intent
from .d4s_merchant import products, sellers
from .d4s_meta import languages, locations
from .d4s_serp import autocomplete, serp, serp_competitors

__all__ = [
    "Client",
    # keywords data / google ads
    "search_volume", "keywords_for_site", "keywords_for_keywords",
    "ad_traffic_by_keywords", "google_trends",
    # labs
    "keyword_ideas", "keyword_suggestions", "keyword_difficulty", "search_intent",
    # serp
    "serp", "serp_competitors", "autocomplete",
    # ads transparency
    "ads_advertisers", "ads_search",
    # merchant / shopping
    "products", "sellers",
    # meta helpers
    "locations", "languages",
    # feature modules
    "d4s_kw_ads", "d4s_labs", "d4s_serp", "d4s_ads_intel", "d4s_merchant", "d4s_meta",
]
__version__ = "0.1.0"

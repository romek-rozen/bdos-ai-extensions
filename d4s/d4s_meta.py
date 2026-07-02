"""
d4s_meta.py — location / language reference helpers.

Resolving the correct ``location_code`` / ``language_code`` is a frequent friction
point with DataForSEO. These GET endpoints list the supported values for the
Google Ads Keywords Data API.
"""

from ._util import get_client

_LOCATIONS = "/v3/keywords_data/google_ads/locations"
_LANGUAGES = "/v3/keywords_data/google_ads/languages"


def locations(country=None, client=None):
    """List supported locations; pass an ISO country code (e.g. "PL") to scope it."""
    path = _LOCATIONS + ("/" + country if country else "")
    return get_client(client).call(path, method="GET")


def languages(client=None):
    """List supported languages and their language codes."""
    return get_client(client).call(_LANGUAGES, method="GET")

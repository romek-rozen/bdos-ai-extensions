"""
d4s_ads_intel.py — Google Ads Transparency Center (competitor ad research).

Data comes from https://adstransparency.google.com/. These endpoints have no
``live`` variant, so they run in task mode (submit → poll → get) via the client's
blocking ``task()`` helper.

Typical flow: find advertisers for a keyword/domain, then pull the ad creatives a
given advertiser is currently running.
"""

from ._util import geo, get_client


def ads_advertisers(keyword=None, target=None, location=None, language=None,
                    client=None, **task_opts):
    """Find advertisers in the Transparency Center by keyword and/or domain.

    Returns ``advertiser_id`` values to feed into ``ads_search``.
    """
    task = geo({}, location, language)
    if keyword is not None:
        task["keyword"] = keyword
    if target is not None:
        task["target"] = target
    return get_client(client).task("/v3/serp/google/ads_advertisers", [task], **task_opts)


def ads_search(advertiser_id, target=None, location=None, language=None,
               client=None, **task_opts):
    """Ad creatives a given advertiser is currently running (desktop/windows only)."""
    task = geo({"advertiser_id": advertiser_id}, location, language)
    if target is not None:
        task["target"] = target
    return get_client(client).task("/v3/serp/google/ads_search", [task], **task_opts)

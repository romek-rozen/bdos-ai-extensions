"""
d4s_merchant.py — Google Shopping / Merchant wrappers (Shopping / PLA campaigns).

Products (prices, sellers) and competing sellers for a product query. These run in
task mode (submit → poll → get) via the client's blocking ``task()`` helper.
"""

from ._util import geo, get_client


def products(keyword, location=None, language=None, client=None, **task_opts):
    """Google Shopping products (prices, sellers) for a product query."""
    task = geo({"keyword": keyword}, location, language)
    return get_client(client).task("/v3/merchant/google/products", [task], **task_opts)


def sellers(keyword, location=None, language=None, client=None, **task_opts):
    """Competing sellers for a product query."""
    task = geo({"keyword": keyword}, location, language)
    return get_client(client).task("/v3/merchant/google/sellers", [task], **task_opts)

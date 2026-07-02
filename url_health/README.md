# `url_health` — final-URL / link health checker

Verify that Google Ads final URLs, sitelinks and other asset URLs actually resolve to a
healthy `200`, capture the full redirect chain, catch `https → http` downgrades, and crawl a
landing-page domain for broken internal links.

## What it does

- **`check(url)`** — fetches a single URL **without auto-following redirects**, walking the
  chain manually (up to ~10 hops) so every hop is recorded. Tells you the final status, the
  full redirect chain, and whether the URL is `healthy` (200, ≤1 redirect hop, no `https → http`
  downgrade).
- **`check_many(urls)`** — the same check over a list; one bad URL never aborts the batch.
- **`crawl(url, max_pages=50)`** — same-domain BFS crawl that follows `<a href>` links, records
  the status of each discovered link, and reports `broken` internal links and `redirects`.

## When to use it

- Before launching / auditing ads: confirm every final URL and sitelink returns `200`.
- Diagnose a redirect problem: see the exact chain and whether a secure page silently drops to
  plain `http`.
- Housekeeping: crawl a landing-page domain and list broken internal links.

## Requirements

- **Pure Python standard library** (`urllib`, `http.client`, `html.parser`). No pip deps, no
  venv, no MCP server, no external services. Runs offline on the BDOS venv.
- **Raw HTTP by design.** Unlike the other page-fetching extensions, `url_health` deliberately
  does **not** route through the `crawl4ai` rendered-browser fetch layer. Checking real HTTP
  status codes and redirect chains is the whole point — a rendered fetch would hide the very
  signals we want (3xx hops, `Location` headers, real 404/500 codes). It sends a browser-like
  `User-Agent` so servers don't serve a stripped response.

## API reference

All functions return a dict with an `ok` key. A **transport** failure (DNS / connection /
timeout) yields `{"ok": False, "error": "..."}`. An **HTTP error status** (e.g. `404`, `500`)
is a valid result with `ok=True` and the real status code — it is not a transport error.

### `check(url, timeout=15) -> dict`

Check a single URL and capture its full redirect chain. Does not follow redirects
automatically; walks the chain manually up to ~10 hops.

| Param | Type | Default | Meaning |
|-------|------|---------|---------|
| `url` | `str` | — | URL to check |
| `timeout` | `int` | `15` | per-hop timeout in seconds |

Returns on transport failure: `{"ok": False, "error": "..."}`.
Otherwise:

| Key | Type | Meaning |
|-----|------|---------|
| `ok` | `bool` | always `True` here |
| `url` | `str` | the original URL |
| `final_url` | `str` | last URL reached |
| `final_status` | `int \| None` | status of the final URL (`None` if the last hop failed to connect) |
| `redirect_chain` | `list[(url, status)]` | one entry per hop before the final response |
| `redirects` | `int` | number of redirect hops |
| `https_final` | `bool` | whether the final URL uses `https` |
| `healthy` | `bool` | `final_status == 200` **and** ≤1 redirect hop **and** no `https → http` downgrade |
| `note` | `str \| None` | human-readable flag (non-200, long chain, downgrade, failed hop) |

### `check_many(urls, timeout=15) -> list[dict]`

Check a list of URLs sequentially. Each element is the dict returned by `check` (always has an
`ok` key). A single bad URL never aborts the batch.

### `crawl(url, max_pages=50, timeout=15) -> dict`

Same-domain BFS crawl starting at `url`. Extracts internal `<a href>` links, records the status
of each discovered link, and stays on the same registrable host (ignoring a leading `www.`).
Caps at `max_pages` fetched HTML pages, dedupes, and skips `mailto:` / `tel:` / `javascript:` /
pure-`#fragment` links. Unlike `check`, the crawl fetch **follows** redirects to reach the final
page for link extraction.

| Param | Type | Default | Meaning |
|-------|------|---------|---------|
| `url` | `str` | — | start URL |
| `max_pages` | `int` | `50` | max HTML pages to fetch |
| `timeout` | `int` | `15` | per-request timeout in seconds |

Returns on failure to fetch the start URL: `{"ok": False, "error": "..."}`.
Otherwise:

| Key | Type | Meaning |
|-----|------|---------|
| `ok` | `bool` | always `True` here |
| `start` | `str` | the start URL (fragment stripped) |
| `pages_checked` | `int` | number of URLs whose status was fetched |
| `broken` | `list[{url, status, found_on}]` | non-200 (or failed) links |
| `redirects` | `list[{url, status, found_on}]` | 3xx responses |
| `ok_count` | `int` | number of URLs that returned `200` |

## Examples

```python
from my.extensions.url_health import check, check_many, crawl

# Single final URL — inspect the redirect chain
r = check("https://example.com/landing")
print(r["final_status"], r["healthy"], r["redirects"])
print(r["redirect_chain"])   # [("http://example.com/landing", 301), ...]

# Batch of sitelinks
for row in check_many(["https://a.com", "https://b.com/x"]):
    if not row["healthy"]:
        print(row["url"], "->", row["note"])

# Crawl a domain for broken internal links
site = crawl("https://example.com", max_pages=50)
print(site["pages_checked"], "checked,", site["ok_count"], "ok")
for b in site["broken"]:
    print(b["status"], b["url"], "(found on", b["found_on"], ")")
```

## Troubleshooting

- **`{"ok": False, "error": "..."}`** — a transport failure (DNS, connection refused, timeout).
  The host is unreachable, not merely returning an error status.
- **`final_status: 404` with `ok: True`** — this is a *valid* result. A 404/500 is a real HTTP
  answer, not a transport error; check `final_status` / `healthy`, not `ok`, for link quality.
- **`healthy: False` but `final_status: 200`** — the URL resolves, but via more than one redirect
  hop or through a `https → http` downgrade. See `note` and `redirect_chain`.
- **`final_status: None`** — the final hop failed to connect mid-chain; earlier hops are still in
  `redirect_chain`.
- **Crawl found fewer pages than expected** — it stops at `max_pages`, stays on the same
  registrable host, and only follows `<a href>` links in HTML responses. Raise `max_pages` if
  needed.
- **A server blocks the request** — `url_health` already sends a browser-like `User-Agent`, but
  it does **not** render JS. If a site only responds to a real browser, that is out of scope here
  (use `crawl4ai` for rendered fetches — but note it hides status codes).

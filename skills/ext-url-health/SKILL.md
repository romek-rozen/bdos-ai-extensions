---
name: ext-url-health
description: Local URL / link health checker for Google Ads final URLs, sitelinks and landing pages (no MCP, pure standard library). Use when the user wants to verify that ad final URLs resolve to a healthy 200, inspect a redirect chain, catch https->http downgrades, batch-check many URLs, or crawl a landing-page domain for broken internal links. Runs fully offline — no pip deps, no venv.
---

# ext-url-health — final-URL & link health checker

Self-contained BDOS extension that checks whether URLs actually resolve. Pure
Python standard library — **no MCP server, no pip deps, no venv** — and it
survives `bdos update` because it lives under `my/`.

Built for Google Ads housekeeping: confirm ad **final URLs**, **sitelinks** and
other asset URLs reach a healthy `200`, expose the full **redirect chain**, flag
`https -> http` downgrades, and **crawl** a landing-page domain for broken links.

## Language

Talk to the user in **their language** (PL or EN — match how they wrote to you).
Code, logs and result keys stay in English.

## Import path (inside BDOS)

```python
from my.extensions.url_health import check, check_many, crawl
```

Run scripts with the **BDOS venv Python** (path in the session banner). This
extension has no venv of its own — it uses only the standard library.

## Check a single URL (full redirect chain)

Redirects are **not** followed automatically — each hop is recorded, so you see
exactly where an ad's final URL ends up.

```python
import sys; sys.stdout.reconfigure(encoding='utf-8')
from my.extensions.url_health import check
r = check("https://example.com/landing")
if r["ok"]:
    print("final:", r["final_url"], "| status:", r["final_status"])
    print("redirects:", r["redirects"], "| healthy:", r["healthy"])
    print("chain:", r["redirect_chain"])
    if r["note"]:
        print("flag:", r["note"])
else:
    print("ERROR:", r["error"])
```

`healthy` is True only when `final_status == 200`, the chain is at most one hop,
and there is no `https -> http` downgrade. A `404` is a **valid result**
(`ok=True`, `final_status=404`), not an error — only transport failures return
`{"ok": False, "error": ...}`.

## Batch-check many URLs (e.g. all sitelinks / all ad final URLs)

```python
import sys; sys.stdout.reconfigure(encoding='utf-8')
from my.extensions.url_health import check_many
urls = [
    "https://example.com/",
    "https://example.com/promo",
    "http://example.com/old-page",
]
rows = check_many(urls)
for row in rows:
    if not row.get("ok"):
        print("DOWN:", row.get("error"))
        continue
    flag = row["note"] or "ok"
    print(f"{row['final_status']}  hops={row['redirects']}  {row['url']}  -> {flag}")
```

Pull the URLs straight from a campaign, then check them — e.g. gather RSA final
URLs / sitelink URLs via `engine.execute(...)` and pass them to `check_many`.

## Crawl a landing-page domain for broken internal links

Same-domain BFS crawl. Extracts internal `<a href>` links, records each link's
status, stays on the same registrable host, dedupes, and skips
`mailto:` / `tel:` / `#fragment` / `javascript:` links.

```python
import sys; sys.stdout.reconfigure(encoding='utf-8')
from my.extensions.url_health import crawl
site = crawl("https://example.com", max_pages=50)
if site["ok"]:
    print("pages checked:", site["pages_checked"], "| ok:", site["ok_count"])
    for b in site["broken"]:
        print("BROKEN", b["status"], b["url"], "(found on", b["found_on"] + ")")
    for rd in site["redirects"]:
        print("REDIRECT", rd["status"], rd["url"])
else:
    print("ERROR:", site["error"])
```

## Result shapes

`check` / `check_many` (one dict per URL):
`ok`, `url`, `final_url`, `final_status`, `redirect_chain` (list of `(url, status)`),
`redirects` (count), `https_final`, `healthy`, `note`. On transport failure:
`{"ok": False, "error": "..."}`.

`crawl`:
`ok`, `start`, `pages_checked`, `broken` (list of `{url, status, found_on}`),
`redirects` (same shape), `ok_count`. On failure to fetch the start URL:
`{"ok": False, "error": "..."}`.

## Notes

- Uses a browser-like User-Agent and a default **15s timeout** (raise `timeout`
  for slow servers).
- Redirect following is capped at ~10 hops to avoid loops.
- A `404`, `410` or `500` is a real, reportable result — not a crash. Only DNS /
  connection / timeout failures come back as `ok=False`.
- Combine with BDOS data: check final URLs of live ads before/after a mutation,
  or crawl a client's site to spot 404s that waste ad clicks.

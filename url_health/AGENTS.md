# AGENTS.md — `url_health`

Final-URL / link health checker for Google Ads: verify final URLs & sitelinks resolve to `200`,
capture the redirect chain, catch `https → http` downgrades, and crawl a domain for broken
internal links.

## Import path

```python
from my.extensions.url_health import check, check_many, crawl
```

Runs in-process on the BDOS venv. Pure standard library — no install step, no MCP server.

## When to reach for it

- Use `url_health` when the question is about **HTTP reachability**: does this final URL / sitelink
  return 200? what does its redirect chain look like? are there broken internal links?
- Use `crawl4ai` instead when you need **rendered content / markdown / extraction** — it hides
  status codes and redirects, so it is the wrong tool for link health.
- Use `landing_audit` for landing-page *quality* signals, `schema_check` for structured data.

## Key calls

| Call | Returns |
|------|---------|
| `check(url, timeout=15)` | `ok, url, final_url, final_status, redirect_chain [(url,status)…], redirects, https_final, healthy, note` |
| `check_many(urls, timeout=15)` | `list` of `check` dicts; one bad URL never aborts the batch |
| `crawl(url, max_pages=50, timeout=15)` | `ok, start, pages_checked, broken [{url,status,found_on}], redirects[], ok_count` |

`healthy` = `final_status == 200` **and** ≤1 redirect hop **and** no `https → http` downgrade.

## Gotchas

- **Raw HTTP by design.** This extension deliberately does **not** use the `crawl4ai` rendered
  fetch layer that the other page extensions route through. Real status codes and redirect chains
  are the whole point — a browser fetch would mask them. Do not "fix" it to use `crawl4ai`.
- **A 404/500 is a valid result** (`ok=True`, real `final_status`). Only DNS/connection/timeout
  failures give `ok=False`. Judge link quality by `healthy` / `final_status`, **not** by `ok`.
- **`check` records redirects, `crawl` follows them.** `check` walks the chain manually (≤~10
  hops, no auto-follow); `crawl`'s page fetch follows redirects to reach the final HTML.
- **`crawl` is capped** at `max_pages` (default 50), stays on the same registrable host (ignores
  leading `www.`), dedupes, and skips `mailto:`/`tel:`/`javascript:`/`#fragment` links.
- **`final_status: None`** means the final hop failed to connect mid-chain.

## Contract reminders

- Every function returns a dict with an **`ok`** key — check `ok` for transport success before
  reading results.
- **Read-only.** Never mutates a Google Ads account; hand any recommended fix to the BDOS
  mutation workflow.
- Match the user's language (PL/EN) in conversation; code and files stay English.

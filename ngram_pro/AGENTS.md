# AGENTS.md — `ngram_pro`

N-gram waste analysis of a **Search Terms report**: split each search term into 1/2/3-word
fragments, aggregate spend/performance per fragment, rank by **wasted spend** (`nscore`), and
return suggested **negative keywords**. Pure stdlib, offline, deterministic.

**Import path inside BDOS:** `my.extensions.ngram_pro` (runs in-process on the BDOS venv).

```python
from my.extensions.ngram_pro import analyze, tokenize, ngrams_of, fold
```

## When to reach for it

| Want | Use this / other |
|---|---|
| Find which words/phrases across search terms burn budget → propose **negatives** | **`ngram_pro`** (`analyze(search_terms, target_cpa=…)`) |
| Group **keyword-research ideas** into ad groups | `keyword_cluster` (`cluster(keywords, …)`) |

`ngram_pro` works on the **Search Terms report** (what users actually searched) to find waste;
`keyword_cluster` works on **keyword ideas** to build ad-group structure. Different inputs,
different goals.

Feed it rows from `engine.execute(entity="search_terms", ...)`.

## Key calls

| Call | Returns |
|---|---|
| `analyze(search_terms, sizes=(1,2,3), target_cpa=None, target_roas=None, min_cost=0.0, min_blocked_terms=1, keywords=None, ga4_by_term=None, negatives_require_zero_conv=True, limit=None, drop_stopwords=True, stopwords=None)` | `{ok, totals, averages, ngrams[], negatives[]}` |
| `tokenize(term)` | `list[str]` — folded, alphanumeric tokens |
| `ngrams_of(tokens, sizes=(1,2,3))` | `list[(text, n)]` contiguous n-grams |
| `fold(text)` | diacritics-insensitive lowercased string |

Each `ngrams[]` entry: `ngram, n, cost, clicks, impressions, conversions, conv_value, ctr,
conv_rate, cpa, roas, blocked_search_terms, blocked_keywords, cost_savings, conv_loss, nscore,
vs_avg{ctr,conv_rate,cpa,roas}, ga4{sessions,engaged_sessions,engagement_rate,bounce_rate}?`.
`negatives[]` = same entries with `nscore > 0` and 0 conversions (unless
`negatives_require_zero_conv=False`), sorted by `cost_savings` desc.

## Gotchas

- **Input row fields drive the metrics.** Accepted keys (first match wins): `term`/`search_term`
  /`text`; `cost`; `clicks`; `impressions`/`impr`; `conversions`/`conv`;
  `conv_value`/`value`/`conversions_value`. Missing keys default to `0` — a metric you forgot to
  map silently reads as zero (and can misrank waste).
- **Ranking = `nscore` (wasted spend), desc.** `target_cpa` → `cost − conv·target_cpa`;
  `target_roas` → `cost − conv_value/target_roas`; else `cost` (0 conv) or `cost − conv_value`.
  Pass a target for meaningful waste; without one, converting terms still score positive when
  `cost > conv_value`.
- **Watch broad 1-grams before excluding.** A high-`nscore` single word can appear in converting
  terms — check `blocked_search_terms` and `conv_loss`; prefer specific 2-/3-grams.
- **Stopwords** (pure function words, PL+EN, single letters) dropped by default; mixed fragments
  kept. `drop_stopwords=False` to disable.
- **Diacritics-insensitive** (`fold`): `łódź` == `lodz`, so spellings aggregate together.
- **`min_cost` / `min_blocked_terms`** filter the table; `blocked_keywords` is `None` unless you
  pass `keywords`; `ga4` block only appears when `ga4_by_term` is given.
- Pure stdlib, **no network**, no MCP — deterministic and offline.

## Contract reminders

1. **Check `ok`** first — empty input returns `{"ok": False, "error": "no search terms provided"}`.
2. **Read-only.** Never exclude/mutate the Google Ads account from here — confirm the
   `negatives` with the user and hand them to the BDOS **mutation workflow**.
3. **Language:** match the user's language (PL/EN) in conversation; code and returned data stay
   **English**.

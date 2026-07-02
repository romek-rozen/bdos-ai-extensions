# `ngram_pro` — n-gram waste analysis → negative keywords

Break every search term in a **Search Terms report** into 1/2/3-word fragments (n-grams),
aggregate spend and performance per fragment, and rank fragments by **wasted spend** so the
worst offenders become **suggested negative keywords**. Pure Python (standard library only) —
offline, deterministic, no network, no MCP.

## What it does / when to use

Answers: *"Which words or phrases across my search terms burn budget without converting?"*

Feed it search-term rows (cost, clicks, impressions, conversions, conv value). It splits each
term into fragments, sums the metrics per fragment across all terms, computes per-fragment CTR
/ conv-rate / CPA / ROAS and how they compare to the account average, scores each fragment by
wasted spend (**nScore**), and hands back a ranked n-gram table plus a `negatives` shortlist
(positive-waste, zero-conversion fragments) ready to review and exclude.

Reach for it when a campaign is bleeding on irrelevant queries (e.g. `tanie`, `darmowe`, `praca`)
and you want data-ranked negative-keyword candidates instead of eyeballing the report.

## Requirements

Pure Python, standard library only. No network, no MCP server, no external dependencies. Runs
in-process on the BDOS venv. The `ext-ngram-pro` skill pulls the rows from BDOS
(`engine.execute(entity="search_terms", ...)`) and, optionally, GA4 engagement metrics.

## API reference

Import inside BDOS:

```python
from my.extensions.ngram_pro import analyze, tokenize, ngrams_of, fold
```

### `analyze(search_terms, sizes=(1, 2, 3), target_cpa=None, target_roas=None, min_cost=0.0, min_blocked_terms=1, keywords=None, ga4_by_term=None, negatives_require_zero_conv=True, limit=None, drop_stopwords=True, stopwords=None) -> dict`

Aggregate search-term rows into a ranked n-gram waste table plus negatives.

| Param | Meaning |
|---|---|
| `search_terms` | list of dicts, each a term + metrics (see input shape below) |
| `sizes` | n-gram sizes to compute (default `1,2,3`) |
| `target_cpa` / `target_roas` | optional targets used by the nScore waste formula |
| `min_cost` | keep only n-grams with at least this cost |
| `min_blocked_terms` | keep only n-grams appearing in at least this many distinct terms |
| `keywords` | optional list of active keyword texts → fills `blocked_keywords` |
| `ga4_by_term` | optional `{term: {sessions, engaged_sessions, bounce_rate}}` merged per n-gram |
| `negatives_require_zero_conv` | only recommend 0-conversion fragments as negatives (default `True`) |
| `limit` | cap the returned n-gram list (after sorting by `nscore` desc) |
| `drop_stopwords` | drop pure function-word fragments (PL+EN, default `True`) |
| `stopwords` | override the default stopword set |

**Input row shape** (accepted keys, first match wins):
`term`/`search_term`/`text`; `cost`; `clicks`; `impressions`/`impr`;
`conversions`/`conv`; `conv_value`/`value`/`conversions_value`. Missing keys default to `0`.

**Returns** `{"ok": True, "totals", "averages", "ngrams": [...], "negatives": [...]}`, or
`{"ok": False, "error": "no search terms provided"}` on empty input.

- `totals` — `{cost, clicks, impressions, conversions, conv_value, terms}`
- `averages` — `{ctr, conv_rate, cpa, roas}` (account-wide; `None` when the denominator is 0)
- `ngrams` — one entry per surviving fragment, sorted by `nscore` desc:

  | Key | Meaning |
  |---|---|
  | `ngram`, `n` | the fragment and its word count |
  | `cost`, `clicks`, `impressions`, `conversions`, `conv_value` | summed metrics |
  | `ctr` | `clicks / impressions` (`None` if no impressions) |
  | `conv_rate` | `conversions / clicks` (`None` if no clicks) |
  | `cpa` | `cost / conversions` (`None` if 0 conversions) |
  | `roas` | `conv_value / cost` (`None` if 0 cost) |
  | `blocked_search_terms` | distinct search terms containing the fragment |
  | `blocked_keywords` | active keywords containing it (`None` if no `keywords` passed) |
  | `cost_savings` | spend you stop if you exclude the fragment (= `cost`) |
  | `conv_loss` | conversions you give up by excluding it (= `conversions`) |
  | `nscore` | wasted spend — the ranking key (see below) |
  | `vs_avg` | `{ctr, conv_rate, cpa, roas}` relative delta vs account average (`None` when undefined; CPA inverted so lower-is-better reads positive) |
  | `ga4` | `{sessions, engaged_sessions, engagement_rate, bounce_rate}` — only when `ga4_by_term` given |

- `negatives` — the subset of `ngrams` with `nscore > 0` (and 0 conversions unless
  `negatives_require_zero_conv=False`), sorted by `cost_savings` desc.

**nScore (wasted spend).** Higher = more wasted spend:

```
with target_cpa:   nscore = cost - conversions * target_cpa
with target_roas:  nscore = cost - conv_value / target_roas
otherwise:         nscore = cost                if conversions == 0
                   nscore = cost - conv_value   otherwise   (net cost)
```

### `tokenize(term) -> list[str]`

Fold (see below), split on any non-alphanumeric run, drop empties. Keeps digits.
`tokenize("Buty  Gore-Tex ŁÓDŹ")` → `["buty", "gore", "tex", "lodz"]`.

### `ngrams_of(tokens, sizes=(1, 2, 3)) -> list[tuple[str, int]]`

Contiguous n-grams as `(text, n)` for each size.
`ngrams_of(["a", "b", "c"])` → `[("a",1), ("b",1), ("c",1), ("a b",2), ("b c",2), ("a b c",3)]`.

### `fold(text) -> str`

Lowercase + diacritics-insensitive folding. Handles NFKD-decomposable accents plus a Latin
fold map for non-decomposable letters (`ł→l`, `đ→d`, `ø→o`, `ß→ss`, `æ→ae`, …). This is why
`łódź` and `lodz` count as the same fragment.

### Worked example

```python
from my.extensions.ngram_pro import analyze

terms = [
    {"term": "tanie buty trekkingowe",   "cost": 100, "clicks": 50, "impressions": 1000, "conversions": 0, "conv_value": 0},
    {"term": "buty trekkingowe damskie", "cost": 80,  "clicks": 40, "impressions": 800,  "conversions": 4, "conv_value": 600},
    {"term": "darmowe buty",             "cost": 30,  "clicks": 20, "impressions": 500,  "conversions": 0, "conv_value": 0},
    {"term": "buty trekkingowe promocja","cost": 50,  "clicks": 25, "impressions": 400,  "conversions": 1, "conv_value": 120},
]

r = analyze(terms, target_cpa=25.0)
r["totals"]["cost"]                       # 260.0
by = {x["ngram"]: x for x in r["ngrams"]}
by["buty"]["blocked_search_terms"]        # 4 — appears in every term
by["buty"]["nscore"]                      # 260 - 5*25 = 135
by["tanie"]["nscore"]                     # 100 — 0 conversions

[x["ngram"] for x in r["negatives"]]      # e.g. ["tanie", "darmowe", ...] sorted by cost_savings
# "buty trekkingowe" is NOT a negative — it converts
```

## Notes

- **Read-only / non-mutating.** `analyze` only reads the rows you pass; it never touches a
  Google Ads account. Treat `negatives` as **candidates** — confirm with the user and hand them
  to the BDOS **mutation workflow** (which validates and applies exclusions). Never exclude from
  here.
- **Watch broad 1-grams before excluding.** A high-`nscore` single word (e.g. `buty`) may sit in
  converting terms too — check `blocked_search_terms` / `conv_loss` first; prefer specific
  2-/3-grams.
- **Stopwords.** Pure function-word fragments (`do`, `z`, `na`, `the`, `and`, single letters …)
  are dropped by default (PL+EN). Mixed fragments like `lampa do` are kept. Pass
  `drop_stopwords=False` or your own `stopwords` to change this.
- **Diacritics.** Folding is diacritics-insensitive (Polish `ł/ó/ż` etc.), so accented and
  ASCII spellings aggregate together.
- **Each term counts once per distinct fragment**, so `blocked_search_terms` reflects distinct
  terms, not repeats.

## Troubleshooting

- **Empty / no rows** → `{"ok": False, "error": "no search terms provided"}`. Check `ok` first.
- **A fragment you expected is missing** → it may be below `min_cost`, appear in fewer than
  `min_blocked_terms` terms, or be a dropped stopword. Lower the thresholds or set
  `drop_stopwords=False`.
- **`cpa`/`roas`/`ctr` is `None`** → the denominator was 0 (no conversions / no cost / no
  impressions), by design.
- **No `blocked_keywords`** (`None`) → you didn't pass `keywords`.

---
name: ext-ngram-pro
description: Advanced n-gram waste analysis of Google Ads search terms → negative keywords. Use when the user wants an n-gram / ngram breakdown of search terms with wasted-spend scoring (nScore), Cost Savings, Conv. Loss, Blocked Keywords/Search Terms, vs-average deltas, optional GA4 engagement columns, and concrete negative-keyword recommendations. Richer than the core search-terms n-gram: it ranks fragments by wasted spend and proposes negatives.
---

# ext-ngram-pro — n-gram waste analysis → negatives

Breaks search terms into 1/2/3-word fragments, aggregates spend and performance per
fragment, ranks them by **wasted spend (nScore)**, and recommends negative keywords — with
Cost Savings, Conv. Loss, Blocked Keywords/Search Terms, vs-average deltas, and optional GA4
engagement metrics.

The math lives in the `ngram_pro` extension (`from my.extensions.ngram_pro import
analyze`); this skill pulls the data from BDOS and presents the result. Talk to the user in
their language (PL/EN); keep code English.

## 0) Confirm scope

Ask which account and campaign(s) and the period. N-gram analysis is meaningless without a
goal — ask for the **target CPA** or **target ROAS** (used for the waste/nScore formula). If
the user has neither, fall back to zero-conversion waste (see below).

## 1) Pull search terms + keywords

```python
import sys; sys.stdout.reconfigure(encoding='utf-8')
from bdos import connect
ctx = connect("ALIAS")

st = ctx.engine.execute(
    entity="search_terms",
    filters=["cost > 0"],          # add campaign scoping, e.g. "campaign.id = 123"
    days=30,                        # or date_from/date_to
)
print("rows:", st.row_count, "| keys:", list(st.data[0].keys()))  # verify field names

# Active positive keywords (optional — fills the Blocked Keywords column)
kw = ctx.engine.execute(entity="keywords", metrics=[],
                        filters=["ad_group_criterion.status = 'ENABLED'"])
keyword_texts = [k.get("keyword") or k.get("text") for k in kw.data]
```

`analyze()` reads these keys per row (first match wins): `term`/`search_term`/`text`; `cost`;
`clicks`; `impressions`/`impr`; `conversions`/`conv`; `conv_value`/`value`. If the engine uses
different names, remap into that shape first (check the printed keys).

## 2) Run the analysis

```python
import sys; sys.stdout.reconfigure(encoding='utf-8')
from bdos import connect
from my.extensions.ngram_pro import analyze
ctx = connect("ALIAS")
st = ctx.engine.execute(entity="search_terms", filters=["cost > 0"], days=30)

result = analyze(
    [dict(r) for r in st.data],
    target_cpa=25.0,        # or target_roas=6.0 ; omit both → zero-conversion waste
    min_cost=5.0,           # ignore tiny fragments
    min_blocked_terms=2,    # fragment must appear in ≥2 terms
    keywords=None,          # pass keyword_texts to fill Blocked Keywords
    limit=100,
    # drop_stopwords=True by default: fragments made only of function words
    # (do/z/w/na/the/and…) are skipped so they don't pollute waste/negatives.
    # Content words like "lampa" are NOT stopwords — judge broad 1-grams by
    # blocked_search_terms before excluding. Pass stopwords=[...] for a custom set.
)
print(result["ok"], "| totals:", result["totals"])
```

## 3) (Optional) GA4 engagement columns

GA4 has no per-search-term dimension, so per-fragment GA4 is **best-effort**: only for terms
you can map to sessions (e.g. via a landing-page or manual mapping). If you have a
`{term: {sessions, engaged_sessions, bounce_rate}}` dict, pass it as `ga4_by_term=...`; each
n-gram then gets a `ga4` block (`sessions, engaged_sessions, engagement_rate, bounce_rate`).
If you can't map GA4 per term, skip these columns — say so, don't fabricate them.

## 4) Present the table

Show the top fragments by nScore. Suggested columns (omit GA4 if not available):

| N-Gram | Cost | Conv. | CPA | ROAS | nScore | Cost Savings | Conv. Loss | Blocked KW | Blocked ST | CTR vs Avg | (GA4: Sessions / Eng. Rate / Bounce) |

Each n-gram entry has: `ngram, n, cost, clicks, impressions, conversions, conv_value, ctr,
conv_rate, cpa, roas, blocked_search_terms, blocked_keywords, cost_savings, conv_loss,
nscore, vs_avg{ctr,conv_rate,cpa,roas}, ga4{...}?`. Group thematically for the user; don't
dump all three n-gram sizes as separate tables. Present metrics by conversion time, ROAS as
% where you show it, and never expose account aliases.

## 5) Recommend negatives — then hand to the mutation workflow

`result["negatives"]` is the ranked list of fragments worth excluding (positive waste, zero
conversions by default), sorted by Cost Savings. For each, show `ngram`, `cost_savings` (what
you save), `conv_loss` (what you give up — 0 for pure-waste), `blocked_search_terms`.

```python
for r in result["negatives"][:20]:
    print(r["ngram"], "| save", r["cost_savings"], "| lose", r["conv_loss"],
          "| terms", r["blocked_search_terms"])
```

**Do not add negatives from here.** Confirm the list with the user, then hand the chosen
fragments to the mutation workflow (`ext`/BDOS `add_negatives`) with explicit scope
(which campaign / shared list, match type). Warn that a short 1-gram (e.g. "buty") can block
a lot — check `blocked_search_terms`/`blocked_keywords` before excluding broad fragments.

## nScore (how waste is scored)

- with `target_cpa`:  `waste = cost − conversions × target_cpa`
- with `target_roas`: `waste = cost − conv_value / target_roas`
- otherwise:          `waste = cost` if 0 conversions, else `cost − conv_value`

Higher nScore = more wasted spend. Prefer a real target; without one, the tool only flags
pure zero-conversion waste.

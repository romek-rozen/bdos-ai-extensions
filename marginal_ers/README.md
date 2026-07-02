# `marginal_ers` — profit-driven bidding (marginal ERS)

Decide whether to **scale a campaign up or down** by comparing its *marginal* Effective
Revenue Share against break-even. Maximizing ROAS/ROI does **not** maximize profit — this
does. Based on the **Zero-ROI / profit-driven** model by
[adequate.digital](https://adequate.digital/model-zero-roi-optymalizacja-profit-driven/).

## The core idea

ROI/ROAS are average-return metrics — the wrong objective for a campaign whose goal is
**total profit**. Profit is maximized by pushing spend until the return on the *next* unit
equals its cost, i.e. until the **marginal** ERS hits break-even.

```
ERS   = Cost / Revenue          Effective Revenue Share; ERS = 1 → costs = revenue, profit = 0
ROAS  = Revenue / Cost = 1/ERS
ROI   = ROAS - 1                fractional; ROI = (Revenue - Cost) / Cost
E     = %ΔClicks / %ΔCPC        price elasticity of traffic
ERSm  = ERS · (1 + 1/E)         marginal ERS — the ERS of the next increment of spend
```

**Decision rule.** Extra investment is profitable while the marginal ERS is below break-even:

```
ERSm < 1   ⇔   ERS < 1/(1+1/E)   ⇔   ROAS > 1 + 1/E   ⇔   ROI > 1/E
```

At the **profit optimum** `ERSm = 1`, so the profit-maximizing bid target is
**`target_roas = 1 + 1/E`**. Counter-intuitively, the *more* elastic the traffic (higher `E`),
the *lower* the optimal ROAS target — you can profitably buy more volume. Because elasticity
differs by campaign, ad group, keyword, and device, a single uniform account-wide ROAS target
is **not** optimal.

See [`docs/references/zero-roi-model.md`](../docs/references/zero-roi-model.md) for the full
theory and attribution.

## What it does / when to use

Answers: *"Should I scale this campaign up or down, and what tROAS should I aim for?"* Feed it
two comparable period snapshots of the same campaign/segment; it measures elasticity, computes
the current and marginal ERS, and returns a verdict (`scale up` / `at optimum` / `cut back`)
plus the profit-optimal target ROAS.

## Requirements

Pure Python, standard library only. No network, no MCP server, no external dependencies. Runs
in-process on the BDOS venv.

## API reference

Import inside BDOS:

```python
from my.extensions.marginal_ers import analyze, decide, elasticity, ers, roas, roi
```

### `analyze(before, after, tolerance=0.05) -> dict`

Full analysis from two period snapshots. Each snapshot is a dict with `cost`, `revenue`, and
`clicks` for the period. CPC is derived as `cost/clicks`; elasticity is measured `before →
after`; the verdict is computed on the **after** (current) ERS.

Returns the `decide()` dict (below) plus a `measured` block:

```python
{
  "ok": True,
  "ers": 0.22, "elasticity": 2.0, "marginal_ers": 0.33,
  "roas": 4.545, "roi": 3.545,
  "target_roas": 1.5, "target_roi": 0.5, "target_ers": 0.667,
  "profitable_to_scale": True,
  "verdict": "scale up",
  "reason": "...",
  "measured": {
    "cpc_before": 1.0, "cpc_after": 1.1,
    "pct_change_clicks": 0.2, "pct_change_cpc": 0.1,
    "ers_before": 0.2, "ers_after": 0.22,
  },
}
```

On bad input returns `{"ok": False, "error": "..."}` (missing keys, non-positive
clicks/revenue, CPC unchanged so elasticity is undefined, etc.).

### `decide(current_ers, e, tolerance=0.05) -> dict`

Use when you already have a current ERS and elasticity `E`. Returns `ok, ers, elasticity,
marginal_ers, roas, roi, target_roas, target_roi, target_ers, profitable_to_scale, verdict,
reason`. Verdict is `at optimum` when `|ERSm - 1| ≤ tolerance`, else `scale up` (`ERSm < 1`) or
`cut back` (`ERSm > 1`). Returns `{"ok": False, "error": ...}` for `e == 0` or `current_ers <= 0`.

### Helpers (return plain floats; raise `ValueError` on bad input)

| Call | Returns |
|---|---|
| `ers(cost, revenue)` | `Cost/Revenue` (raises if `revenue <= 0`) |
| `roas(cost, revenue)` | `Revenue/Cost` (raises if `cost <= 0`) |
| `roi(cost, revenue)` | `ROAS - 1` (raises if `cost <= 0`) |
| `elasticity(clicks_before, clicks_after, cpc_before, cpc_after)` | `E = %ΔClicks / %ΔCPC` |
| `elasticity_from_revenue_ers(revenue_before, revenue_after, ers_before, ers_after)` | `E = %ΔRevenue / %ΔERS` |
| `marginal_ers(current_ers, e)` | `ERS · (1 + 1/E)` |
| `target_roas(e)` | `1 + 1/E` |
| `target_roi(e)` | `1/E` |
| `target_ers(e)` | `1 / (1 + 1/E)` |

### Worked example

CPC rose 1.00 → 1.10 (+10%) while clicks grew 1000 → 1200 (+20%), so `E = 20%/10% = 2` —
fairly elastic. Current ERS = 1320/6000 = **0.22**.

```python
from my.extensions.marginal_ers import analyze
r = analyze({"cost": 1000, "revenue": 5000, "clicks": 1000},   # before
            {"cost": 1320, "revenue": 6000, "clicks": 1200})   # after
r["elasticity"]   # 2.0
r["marginal_ers"] # 0.22 * (1 + 1/2) = 0.33  → < 1
r["target_roas"]  # 1 + 1/2 = 1.5
r["verdict"]      # "scale up"
```

`ERSm = 0.33 < 1`, and the current ROAS (4.55) is well above the target (1.50) — so the
campaign is **under-invested**: raise bids/budget/lower the tROAS toward `1.5` to capture more
profitable volume.

## Feeding the result into BDOS

This extension is **read/analyze only** — it never touches a Google Ads account. Treat
`target_roas` as a **recommendation**. To act on it, hand the value to the BDOS **mutation
workflow** (which validates and applies changes), e.g. as a new tROAS bidding target — after
confirming with the user. Never mutate bids directly from here.

## Reference

- [Zero-ROI / profit-driven bidding model](../docs/references/zero-roi-model.md) — theory,
  assumptions, and attribution (adequate.digital).

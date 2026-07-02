---
name: ext-marginal-ers
description: Profit-driven bidding decisions using marginal ERS and price elasticity (the "Zero-ROI model"). Use when the user asks whether to scale a campaign up or down, what target ROAS/tROAS maximizes PROFIT (not ROAS), whether extra spend is still profitable, price elasticity of traffic, marginal ERS/ROI, or "is raising bids/budget worth it". Pure Python math, no deps, no MCP.
---

# ext-marginal-ers — profit-driven bidding (marginal ERS)

Maximizing ROAS or ROI does **not** maximize profit. Profit is maximized by pushing
investment until the **marginal** return equals its cost. This extension implements the
profit-driven "Zero-ROI" model (adequate.digital) to tell you whether a campaign is
under-invested, at its optimum, or over-invested — and what target ROAS to aim for.

Talk to the user in their language (PL/EN); keep code and files English.

## The model (why ROAS alone misleads)

```
ERS   = Cost / Revenue          # Effective Revenue Share; ERS = 1 → break-even
ROAS  = Revenue / Cost = 1/ERS
ROI   = ROAS - 1                # fractional

E     = elasticity = %ΔClicks / %ΔCPC     # how fast traffic grows vs the price paid
ERSm  = ERS · (1 + 1/E)         # MARGINAL ERS — the decision variable
```

**Scaling up is profitable while `ERSm < 1`**, which is equivalent to:

```
ROAS > 1 + 1/E        (target ROAS for the profit optimum)
ROI  > 1/E
ERS  < 1 / (1 + 1/E)
```

At the optimum `ERSm = 1`, i.e. **target ROAS = 1 + 1/E**. A high elasticity (traffic
responds strongly to bids) means the optimal ROAS target is *lower* — you can afford to
buy more traffic. Source: <https://adequate.digital/model-zero-roi-optymalizacja-profit-driven/>

## Quick calculation

```python
import sys; sys.stdout.reconfigure(encoding='utf-8')
from my.extensions.marginal_ers import analyze

# Two period snapshots of the same campaign/segment (before scaling vs after):
r = analyze(
    before={"cost": 1000, "revenue": 5000, "clicks": 1000},
    after ={"cost": 1320, "revenue": 6000, "clicks": 1200},
)
print(r["ok"], r["verdict"], "| E =", round(r["elasticity"], 2),
      "| ERSm =", round(r["marginal_ers"], 3),
      "| target ROAS =", round(r["target_roas"], 2))
print(r["reason"])
```

`analyze()` derives CPC = cost/clicks per period, measures elasticity between the periods,
and judges the AFTER (current) state. Result keys: `ers, elasticity, marginal_ers, roas,
roi, target_roas, target_roi, target_ers, profitable_to_scale, verdict` (`scale up` /
`at optimum` / `cut back`), `reason`, and `measured` (cpc_before/after, %Δ, ers_before/after).

## If you already know elasticity and current ERS

```python
import sys; sys.stdout.reconfigure(encoding='utf-8')
from my.extensions.marginal_ers import decide
r = decide(current_ers=0.20, e=2.0)   # ERS 0.20 → ROAS 5.0, elasticity 2
print(r["verdict"], r["target_roas"])  # "scale up", 1.5
```

Building blocks are also exposed: `ers(cost, revenue)`, `roas(...)`, `roi(...)`,
`elasticity(clicks_before, clicks_after, cpc_before, cpc_after)`,
`elasticity_from_revenue_ers(...)`, `marginal_ers(ers, E)`, `target_roas/roi/ers(E)`.

## Using it with real BDOS campaign data

Pull two comparable periods for a campaign (same length, e.g. before vs after a bid/budget
change) and feed the totals in. Elasticity needs a genuine change in CPC/clicks between the
periods — compare a period before a scale-up to the period after.

```python
import sys; sys.stdout.reconfigure(encoding='utf-8')
from bdos import connect
from my.extensions.marginal_ers import analyze

ctx = connect("ALIAS")
def totals(date_from, date_to, campaign_id):
    res = ctx.engine.execute(entity="campaigns",
        fields=["id"], filters=[f"id = {campaign_id}", "cost > 0"],
        date_from=date_from, date_to=date_to)
    row = res.data[0]
    return {"cost": row["cost"], "revenue": row.get("conv_value", 0), "clicks": row["clicks"]}

before = totals("2026-05-01", "2026-05-31", 123)
after  = totals("2026-06-01", "2026-06-30", 123)
r = analyze(before, after)
print(r["verdict"], "→ target ROAS", round(r["target_roas"], 2))
```

Check the exact field keys with `list(res.data[0].keys())` — revenue is usually
`conv_value`. Only compare periods where spend actually changed, else elasticity is undefined.

## Turning the verdict into action (BDOS)

- **scale up** → the profit optimum is at a *lower* ROAS than current; you can raise
  budget/bids or **lower the tROAS target toward `target_roas` (= 1 + 1/E)** to buy more
  profitable volume. Do it as one change at a time (see the mutation rules) and monitor.
- **at optimum** → hold; current settings are near profit-maximizing.
- **cut back** → last clicks cost more than they return; raise tROAS / lower budget.

Never mutate from this skill directly — hand the recommended tROAS to the mutation workflow
and confirm scope first.

## Caveats

- **Search / manual-CPC campaigns only.** The model assumes CPC is the bidding lever and
  traffic rises with price (E > 0). For **PMax / Shopping / Demand Gen**, CPC isn't the lever,
  so elasticity is unreliable — if `analyze` returns `verdict: "inconclusive"` (negative E,
  i.e. clicks and CPC moved in opposite directions), do not give a scale verdict; it usually
  means the change was budget/seasonal, not bid-driven, or the campaign type doesn't fit.
- Assumes conversion value per conversion and conversion rate stay roughly constant as you
  scale (same audience quality). State this when advising.
- Elasticity from two noisy periods is an estimate — prefer longer, stable, comparable
  windows; ignore seasonal peaks/troughs (cross-check with the seasonality skill).
- Undefined when CPC or spend didn't change between periods (returns `ok: False`).

# AGENTS.md — `marginal_ers`

Profit-driven bidding math: decide **scale up / at optimum / cut back** for a campaign via
*marginal* ERS and price elasticity (the "Zero-ROI" model). Maximizing ROAS ≠ maximizing profit.

**Import path inside BDOS:** `my.extensions.marginal_ers` (runs in-process on the BDOS venv).

```python
from my.extensions.marginal_ers import analyze, decide
```

## When to reach for it

User asks *"should I scale this campaign up or down?"*, *"what's the profit-optimal tROAS?"*,
or hands you two period snapshots of a campaign and wants a bidding recommendation.

## Key calls

| Call | Returns |
|---|---|
| `analyze(before, after)` | `verdict`, `target_roas (=1+1/E)`, `ers`, `elasticity`, `marginal_ers`, `roas`, `roi`, `profitable_to_scale`, `reason`, `measured` |
| `decide(current_ers, e)` | same as `analyze` (minus `measured`) when you already have ERS + elasticity |
| `elasticity(clk_b, clk_a, cpc_b, cpc_a)` | `E = %ΔClicks / %ΔCPC` |
| `ers / roas / roi(cost, revenue)` | the base metrics |
| `target_roas(e)` / `target_roi(e)` / `target_ers(e)` | profit-optimal thresholds |

Snapshots for `analyze` are dicts: `{"cost": ..., "revenue": ..., "clicks": ...}`.

## Gotchas

- `analyze` needs **two** period snapshots where spend genuinely changed (CPC must differ, or
  elasticity is undefined → `{"ok": False}`).
- Elasticity assumes **constant revenue-per-conversion and conversion rate** as you scale;
  breaks if scaling reaches lower-quality audiences — state this when advising.
- Verdict semantics: `scale up` (`ERSm < 1`, under-invested), `at optimum` (`|ERSm-1| ≤ 0.05`,
  hold), `cut back` (`ERSm > 1`, over-invested).
- Pure math, **no network**, no MCP — deterministic and offline.
- Elasticity varies by campaign/ad group/keyword/device; don't apply one target account-wide.

## Contract reminders

- Every function returns an `ok`-keyed dict (helpers return floats / raise `ValueError`).
  **Check `ok`** before using results.
- Output is a **recommendation**: hand `target_roas` to the BDOS **mutation workflow** for a
  tROAS change — **never mutate the Google Ads account** from here.
- Match the user's language (PL/EN) in conversation; code and files stay **English**.

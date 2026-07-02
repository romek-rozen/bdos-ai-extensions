# Reference — the Zero-ROI / profit-driven bidding model

Theory behind the [`marginal_ers`](../EXTENSIONS.md#marginal_ers) extension.

**Source & attribution:** this model is by **adequate.digital**.
Read the original article (Polish, with the full derivation and charts):
<https://adequate.digital/model-zero-roi-optymalizacja-profit-driven/>
Related: <https://adequate.digital/optymalny-poziom-kampanii-e-commerce/> (the `ROI > 1/E` model).

The summary below is a distilled, English restatement for implementers — the formulas and
credit belong to the source above.

## The core idea

ROI is an investment-appraisal metric; it is the wrong objective for online campaigns. The
goal is to maximize **profit**, not the rate of return. Decisions to raise or lower bids
should be made on **marginal** profit per conversion — the return on the *next* unit of spend,
not the average.

## Definitions

```
ERS   = Cost / Revenue          Effective Revenue Share; ERS = 1 → costs = revenue, profit = 0
ROAS  = Revenue / Cost = 1/ERS
ROI   = ROAS - 1                fractional; ROI = (Revenue - Cost) / Cost
```

**Elasticity** measures how fast a campaign's effect (traffic) grows relative to the price
paid for it. Under two assumptions — constant revenue per conversion and constant conversion
rate as you scale — it reduces to a traffic-vs-price relationship:

```
E = %ΔClicks / %ΔCPC
```

Example: CPC 10 → 11 zł (+10%), clicks 1000 → 1200 (+20%) → **E = 20% / 10% = 2** (traffic
grows twice as fast as CPC — fairly elastic).

## Marginal ERS and the decision rule

The marginal ERS — the ERS of the *next* increment of spend — is:

```
ERSm = ERS · (1 + 1/E)
```

Additional investment is profitable as long as the marginal ERS is below break-even:

```
ERSm < 1
   ⇔  ERS  < 1 / (1 + 1/E)
   ⇔  ROAS > 1 + 1/E
   ⇔  ROI  > 1/E
```

At the **profit optimum**, `ERSm = 1`, i.e. the profit-maximizing target is
**ROAS = 1 + 1/E**. Note the counter-intuitive consequence: the more elastic the traffic
(higher `E`), the *lower* the optimal ROAS target — you can profitably buy more volume.

## Under- vs over-investment

- **ROI > 1/E** → under-investment: raise bids / budget / lower tROAS toward `1 + 1/E`.
- **ROI = 1/E** → optimum: hold.
- **ROI < 1/E** → over-investment: the last clicks cost more than they return; cut back.

Because elasticity differs across campaigns, ad groups, keywords, devices, etc., a single
uniform target ROI/ROAS across a whole account is **not** optimal — targets should vary with
each dimension's price elasticity.

## Practical notes

- Smart bidding expresses the price of traffic as ROAS/ERS rather than CPC, so the same logic
  applies to a tROAS target, not just manual CPC.
- Estimating `E` needs two comparable periods where spend genuinely changed. Prefer longer,
  stable windows and avoid seasonal peaks/troughs.
- The constant-conversion-value and constant-conversion-rate assumptions break if scaling
  reaches lower-quality audiences; state this when advising.

## How `marginal_ers` implements this

`analyze(before, after)` derives CPC = cost/clicks per period, measures `E`, computes the
current ERS, and returns `ERSm`, the verdict (`scale up` / `at optimum` / `cut back`), and the
profit-optimal `target_roas = 1 + 1/E` to feed into a bidding change. See
[`docs/EXTENSIONS.md`](../EXTENSIONS.md#marginal_ers).

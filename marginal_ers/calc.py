"""
calc.py — marginal ERS / profit-driven bidding math (the "Zero-ROI model").

Based on the profit-driven optimization model by adequate.digital
(https://adequate.digital/model-zero-roi-optymalizacja-profit-driven/).

Core idea: maximizing ROAS/ROI does NOT maximize profit. Profit is maximized by
pushing investment until the *marginal* return equals its cost. The marginal
Effective Revenue Share (ERSm) is the decision variable.

Definitions
-----------
    ERS   = Cost / Revenue           (Effective Revenue Share; ERS = 1 → break-even)
    ROAS  = Revenue / Cost = 1 / ERS
    ROI   = ROAS - 1                 (fractional; ROI = (Revenue - Cost) / Cost)

    E     = elasticity = %ΔClicks / %ΔCPC
            (how fast traffic grows relative to the price paid for it)

    ERSm  = ERS * (1 + 1/E)          (marginal ERS)

Decision rule
-------------
    Scaling investment up is profitable while  ERSm < 1, equivalently:
        ERS  < 1 / (1 + 1/E)
        ROAS > 1 + 1/E
        ROI  > 1 / E

At the profit optimum ERSm = 1, i.e. target ROAS = 1 + 1/E. Beyond it you are
over-investing: extra revenue costs more than it returns.

All functions return plain floats or dicts; the high-level ones return an
`ok`-keyed dict for consistency with the other BDOS extensions.
"""

from __future__ import annotations

# Verdict when |ERSm - 1| is within this band → treat as "at optimum".
OPTIMUM_TOLERANCE = 0.05


def ers(cost: float, revenue: float) -> float:
    """Effective Revenue Share = Cost / Revenue. Raises on revenue <= 0."""
    if revenue <= 0:
        raise ValueError("revenue must be > 0 to compute ERS")
    return cost / revenue


def roas(cost: float, revenue: float) -> float:
    """Return On Ad Spend = Revenue / Cost. Raises on cost <= 0."""
    if cost <= 0:
        raise ValueError("cost must be > 0 to compute ROAS")
    return revenue / cost


def roi(cost: float, revenue: float) -> float:
    """Fractional ROI = (Revenue - Cost) / Cost = ROAS - 1."""
    if cost <= 0:
        raise ValueError("cost must be > 0 to compute ROI")
    return (revenue - cost) / cost


def _pct_change(before: float, after: float) -> float:
    if before == 0:
        raise ValueError("cannot compute a percentage change from a zero baseline")
    return (after - before) / before


def elasticity(clicks_before: float, clicks_after: float,
               cpc_before: float, cpc_after: float) -> float:
    """Elasticity E = %ΔClicks / %ΔCPC.

    Example from the source article: CPC 10→11 (+10%), clicks 1000→1200 (+20%)
    → E = 20% / 10% = 2 (traffic grows twice as fast as CPC).
    """
    d_cpc = _pct_change(cpc_before, cpc_after)
    if d_cpc == 0:
        raise ValueError("CPC did not change — elasticity is undefined")
    return _pct_change(clicks_before, clicks_after) / d_cpc


def elasticity_from_revenue_ers(revenue_before: float, revenue_after: float,
                                ers_before: float, ers_after: float) -> float:
    """Elasticity via the original definition E = (%ΔRevenue) / (%ΔERS)."""
    d_ers = _pct_change(ers_before, ers_after)
    if d_ers == 0:
        raise ValueError("ERS did not change — elasticity is undefined")
    return _pct_change(revenue_before, revenue_after) / d_ers


def marginal_ers(current_ers: float, e: float) -> float:
    """Marginal ERS = ERS * (1 + 1/E). Raises on E == 0."""
    if e == 0:
        raise ValueError("elasticity E must be non-zero")
    return current_ers * (1 + 1 / e)


def target_roas(e: float) -> float:
    """Profit-optimal ROAS target = 1 + 1/E (where ERSm = 1)."""
    if e == 0:
        raise ValueError("elasticity E must be non-zero")
    return 1 + 1 / e


def target_roi(e: float) -> float:
    """Profit-optimal ROI threshold = 1/E."""
    if e == 0:
        raise ValueError("elasticity E must be non-zero")
    return 1 / e


def target_ers(e: float) -> float:
    """Profit-optimal ERS threshold = 1 / (1 + 1/E)."""
    return 1 / target_roas(e)


def decide(current_ers: float, e: float, tolerance: float = OPTIMUM_TOLERANCE) -> dict:
    """Turn a current ERS and elasticity into a profit-driven verdict.

    Returns a dict:
        ok               True
        ers              current ERS
        elasticity       E
        marginal_ers     ERSm = ERS*(1+1/E)
        roas             1/ERS (current)
        roi              ROAS-1 (current)
        target_roas      1+1/E   (raise bids/tROAS toward this to reach optimum)
        target_roi       1/E
        target_ers       1/(1+1/E)
        profitable_to_scale  True while ERSm < 1
        verdict          "scale up" | "at optimum" | "cut back"
        reason           human-readable explanation
    """
    if e == 0:
        return {"ok": False, "error": "elasticity E must be non-zero"}
    if current_ers <= 0:
        return {"ok": False, "error": "current ERS must be > 0"}

    cur_roas0 = 1 / current_ers
    if e < 0:
        # The model assumes traffic rises with price (E > 0). Negative elasticity
        # means clicks and CPC moved in opposite directions between the periods —
        # so this is not a clean bid-driven change. Common causes: a PMax/Shopping
        # campaign where CPC isn't the bidding lever, a budget-only or seasonal
        # change, or noise. The marginal-ERS verdict does not apply.
        return {
            "ok": True,
            "ers": current_ers,
            "elasticity": e,
            "marginal_ers": None,
            "roas": cur_roas0,
            "roi": cur_roas0 - 1,
            "target_roas": None,
            "target_roi": None,
            "target_ers": None,
            "profitable_to_scale": None,
            "verdict": "inconclusive",
            "reason": (f"elasticity is negative (E={e:.2f}): clicks and CPC moved in "
                       f"opposite directions, so the price→traffic model doesn't apply. "
                       f"Likely not a clean bid-driven change (budget/seasonality) or a "
                       f"PMax/Shopping campaign where CPC isn't the bidding lever. Compare "
                       f"two Search periods that differ mainly by bid."),
        }

    ersm = marginal_ers(current_ers, e)
    cur_roas = 1 / current_ers
    cur_roi = cur_roas - 1
    t_roas = target_roas(e)

    if abs(ersm - 1) <= tolerance:
        verdict = "at optimum"
        reason = (f"marginal ERS ≈ 1 (={ersm:.3f}); the campaign sits near its "
                  f"profit optimum — hold.")
    elif ersm < 1:
        verdict = "scale up"
        reason = (f"marginal ERS {ersm:.3f} < 1: extra investment still adds profit. "
                  f"Current ROAS {cur_roas:.2f} is above the target {t_roas:.2f} "
                  f"(=1+1/E) — raise bids/budget/tROAS toward the optimum.")
    else:
        verdict = "cut back"
        reason = (f"marginal ERS {ersm:.3f} > 1: you are over-investing — the last "
                  f"clicks cost more than they return. Current ROAS {cur_roas:.2f} is "
                  f"below the target {t_roas:.2f} (=1+1/E) — lower bids/tROAS.")

    return {
        "ok": True,
        "ers": current_ers,
        "elasticity": e,
        "marginal_ers": ersm,
        "roas": cur_roas,
        "roi": cur_roi,
        "target_roas": t_roas,
        "target_roi": target_roi(e),
        "target_ers": target_ers(e),
        "profitable_to_scale": ersm < 1,
        "verdict": verdict,
        "reason": reason,
    }


def analyze(before: dict, after: dict, tolerance: float = OPTIMUM_TOLERANCE) -> dict:
    """Full analysis from two period snapshots of the same campaign/segment.

    Each snapshot is a dict with:
        cost      spend in the period
        revenue   conversion value (revenue) in the period
        clicks    clicks in the period
    CPC is derived as cost/clicks. Elasticity is measured between the two periods
    (before → after), and the verdict is computed on the AFTER (current) ERS.

    Returns the `decide()` dict plus measured inputs, or {"ok": False, "error"}.
    """
    try:
        for label, snap in (("before", before), ("after", after)):
            for key in ("cost", "revenue", "clicks"):
                if key not in snap:
                    return {"ok": False, "error": f"{label} snapshot missing '{key}'"}
            if snap["clicks"] <= 0:
                return {"ok": False, "error": f"{label} clicks must be > 0"}
            if snap["revenue"] <= 0:
                return {"ok": False, "error": f"{label} revenue must be > 0"}

        cpc_before = before["cost"] / before["clicks"]
        cpc_after = after["cost"] / after["clicks"]
        e = elasticity(before["clicks"], after["clicks"], cpc_before, cpc_after)
        current_ers = ers(after["cost"], after["revenue"])

        result = decide(current_ers, e, tolerance=tolerance)
        if not result.get("ok"):
            return result
        result["measured"] = {
            "cpc_before": cpc_before,
            "cpc_after": cpc_after,
            "pct_change_clicks": _pct_change(before["clicks"], after["clicks"]),
            "pct_change_cpc": _pct_change(cpc_before, cpc_after),
            "ers_before": ers(before["cost"], before["revenue"]),
            "ers_after": current_ers,
        }
        return result
    except ValueError as exc:
        return {"ok": False, "error": str(exc)}

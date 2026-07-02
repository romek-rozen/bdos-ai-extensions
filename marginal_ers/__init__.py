"""
marginal_ers — profit-driven bidding math (marginal ERS / "Zero-ROI model").

Decide whether a campaign should be scaled up or reined in by comparing its
*marginal* Effective Revenue Share against break-even, using price elasticity of
traffic. Maximizing ROAS/ROI does not maximize profit — this does.

Model: adequate.digital — Zero-ROI / profit-driven optimization.

Public API (import path inside BDOS):
    from my.extensions.marginal_ers import analyze, decide, elasticity, ers, roas, roi

    # From two period snapshots of a campaign:
    analyze({"cost": 1000, "revenue": 5000, "clicks": 1000},
            {"cost": 1320, "revenue": 6000, "clicks": 1200})
"""

from .calc import (
    analyze,
    decide,
    elasticity,
    elasticity_from_revenue_ers,
    ers,
    marginal_ers,
    roas,
    roi,
    target_ers,
    target_roas,
    target_roi,
)

__all__ = [
    "analyze", "decide", "elasticity", "elasticity_from_revenue_ers",
    "ers", "roas", "roi", "marginal_ers", "target_roas", "target_roi", "target_ers",
]
__version__ = "0.1.0"

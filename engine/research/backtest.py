"""Market-neutral daily long-short backtest with India-specific costs.

Weights w[t] are formed from the signal at t's close and earn fwd[t] (t+1 open -> t+2 open).
Long leg sums to +1, short leg to -1 (gross 2). Return = long-leg return minus short-leg return.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class LegCosts:
    """One-way cost in basis points per unit of notional traded, split by buy/sell."""
    buy_bps: float
    sell_bps: float

    @property
    def avg_bps(self) -> float:
        return (self.buy_bps + self.sell_bps) / 2


def _statutory(stt_buy, stt_sell, stamp_buy, exch, brokerage, sebi=0.01, gst=0.18):
    taxed = (exch + brokerage + sebi) * gst
    return (stt_buy + stamp_buy + exch + brokerage + sebi + taxed,
            stt_sell + exch + brokerage + sebi + taxed)


# Rates in bps (FY2025 schedule). Long leg = cash delivery; short leg = single-stock futures,
# because an overnight cash short is not allowed in India.
_DEL_BUY, _DEL_SELL = _statutory(stt_buy=10.0, stt_sell=10.0, stamp_buy=1.5, exch=0.297, brokerage=0.0)
_FUT_BUY, _FUT_SELL = _statutory(stt_buy=0.0, stt_sell=2.0, stamp_buy=0.2, exch=0.173, brokerage=0.3)


@dataclass(frozen=True)
class CostModel:
    slippage_bps: float = 7.5
    multiplier: float = 1.0
    long_leg: LegCosts = field(default_factory=lambda: LegCosts(_DEL_BUY, _DEL_SELL))
    short_leg: LegCosts = field(default_factory=lambda: LegCosts(_FUT_BUY, _FUT_SELL))

    def long_bps(self) -> float:
        return (self.long_leg.avg_bps + self.slippage_bps) * self.multiplier

    def short_bps(self) -> float:
        return (self.short_leg.avg_bps + self.slippage_bps) * self.multiplier


def _capped_leg(raw: pd.DataFrame, cap: float, iters: int = 20) -> pd.DataFrame:
    """Normalise each row to sum 1, cap every name at `cap`, redistribute the excess to uncapped
    names. If the row has fewer than 1/cap names, it ends up at n*cap (< 1) instead of breaking the cap."""
    w = raw.div(raw.sum(axis=1), axis=0).fillna(0.0)
    for _ in range(iters):
        over = w > cap + 1e-12
        if not over.any().any():
            break
        excess = (w - cap).where(over, 0.0).sum(axis=1)
        w = w.where(~over, cap)
        free = w.where((w > 0) & (w < cap - 1e-12), 0.0)
        share = free.div(free.sum(axis=1).replace(0, np.nan), axis=0).fillna(0.0)
        w = w + share.mul(excess, axis=0)
    return w


def build_weights(score: pd.DataFrame, tradeable: pd.DataFrame, frac: float = 0.2,
                  max_weight: float = 0.04, rebalance_every: int = 1, offset: int = 0,
                  inv_vol: pd.DataFrame | None = None) -> pd.DataFrame:
    s = score.where(tradeable)
    n = s.notna().sum(axis=1)
    pct = s.rank(axis=1, pct=True)
    long = (pct > 1 - frac).astype(float)
    short = (pct <= frac).astype(float)
    if inv_vol is not None:
        long, short = long * inv_vol, short * inv_vol
    long, short = _capped_leg(long, max_weight), _capped_leg(short, max_weight)
    # if a leg cannot be fully invested under the cap, shrink the other leg to stay dollar-neutral
    size = pd.concat([long.sum(axis=1), short.sum(axis=1)], axis=1).min(axis=1)
    long = long.mul(size / long.sum(axis=1), axis=0)
    short = short.mul(size / short.sum(axis=1), axis=0)
    w = (long - short).where(n >= 20, 0.0).fillna(0.0)
    if rebalance_every > 1:
        keep = (np.arange(len(w)) + offset) % rebalance_every == 0
        w = w.where(pd.Series(keep, index=w.index), np.nan).ffill().fillna(0.0)
    return w


def run(weights: pd.DataFrame, fwd: pd.DataFrame, costs: CostModel) -> pd.DataFrame:
    r = fwd.reindex_like(weights)
    # a held name with no next-day price (suspension / delisting in data) is marked flat
    gross = (weights * r.fillna(0.0)).sum(axis=1)
    long_w, short_w = weights.clip(lower=0), (-weights).clip(lower=0)
    long_traded = long_w.diff().fillna(long_w).abs().sum(axis=1)
    short_traded = short_w.diff().fillna(short_w).abs().sum(axis=1)
    cost = (long_traded * costs.long_bps() + short_traded * costs.short_bps()) / 1e4
    # one-way turnover as a fraction of the gross book (1.0 = whole book replaced)
    turnover = (long_traded + short_traded) / 4
    out = pd.DataFrame({"gross": gross, "cost": cost, "net": gross - cost, "turnover": turnover})
    # days with no book at all (e.g. before the first walk-forward model exists) are not trading days
    return out.where(weights.abs().sum(axis=1) > 0)


def metrics(daily: pd.Series, turnover: pd.Series | None = None, cost: pd.Series | None = None,
            benchmark: pd.Series | None = None) -> dict:
    d = daily.dropna()
    if len(d) < 20:
        return {}
    ann_ret, ann_vol = d.mean() * 252, d.std() * np.sqrt(252)
    eq = d.cumsum()
    out = {"ann_return": ann_ret, "ann_vol": ann_vol, "sharpe": ann_ret / ann_vol if ann_vol else np.nan,
           "max_drawdown": float((eq - eq.cummax()).min()), "n_days": len(d)}
    if turnover is not None:
        out["avg_daily_turnover"] = float(turnover.reindex(d.index).mean())
    if cost is not None:
        out["ann_cost"] = float(cost.reindex(d.index).mean() * 252)
    if benchmark is not None:
        b = benchmark.reindex(d.index)
        out["corr_to_nifty200"] = float(d.corr(b))
    return out

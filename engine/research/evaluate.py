"""Single-signal evaluation: rank IC, ICIR, t-stat, decile spread, IC decay, signal correlations."""
from __future__ import annotations

import numpy as np
import pandas as pd
from scipy import stats


def daily_ic(signal: pd.DataFrame, fwd: pd.DataFrame, min_names: int = 30) -> pd.Series:
    """Spearman rank correlation per day (ranks then row-wise Pearson), on names with both values."""
    s, r = signal.align(fwd, join="inner")
    mask = s.notna() & r.notna()
    s, r = s.where(mask).rank(axis=1), r.where(mask).rank(axis=1)
    s = s.sub(s.mean(axis=1), axis=0)
    r = r.sub(r.mean(axis=1), axis=0)
    ic = (s * r).sum(axis=1) / np.sqrt((s ** 2).sum(axis=1) * (r ** 2).sum(axis=1))
    return ic[mask.sum(axis=1) >= min_names].dropna()


def ic_summary(ic: pd.Series) -> dict:
    n = len(ic)
    if n < 2:
        return {"ic_mean": np.nan, "ic_std": np.nan, "icir_ann": np.nan, "t_stat": np.nan, "n_days": n}
    m, sd = ic.mean(), ic.std()
    return {"ic_mean": m, "ic_std": sd, "icir_ann": m / sd * np.sqrt(252), "t_stat": m / sd * np.sqrt(n),
            "hit_rate": (ic > 0).mean(), "n_days": n}


def quantile_spread(signal: pd.DataFrame, fwd: pd.DataFrame, q: int = 10, min_names: int = 30) -> pd.Series:
    """Daily mean fwd return of top quantile minus bottom quantile."""
    s, r = signal.align(fwd, join="inner")
    mask = s.notna() & r.notna()
    pct = s.where(mask).rank(axis=1, pct=True)
    top = r.where(pct > 1 - 1 / q).mean(axis=1)
    bot = r.where(pct <= 1 / q).mean(axis=1)
    return (top - bot)[mask.sum(axis=1) >= min_names].dropna()


def ic_decay(signal: pd.DataFrame, open_: pd.DataFrame, lags=(1, 2, 5, 10)) -> dict:
    """IC against the single-day return `lag` days ahead (non-overlapping definition)."""
    from .data import forward_returns
    return {lag: daily_ic(signal, forward_returns(open_, 1, delay=lag - 1)).mean() for lag in lags}


def signal_correlation(signals: dict[str, pd.DataFrame]) -> pd.DataFrame:
    """Average daily cross-sectional rank correlation between each pair of signals."""
    names = list(signals)
    out = pd.DataFrame(np.eye(len(names)), index=names, columns=names)
    for i, a in enumerate(names):
        for b in names[i + 1:]:
            c = daily_ic(signals[a], signals[b]).mean()
            out.loc[a, b] = out.loc[b, a] = c
    return out


def by_period(series: pd.Series, periods: dict[str, tuple[str, str]]) -> dict:
    return {k: series.loc[a:b] for k, (a, b) in periods.items()}


def multiple_testing_threshold(n_tests: int, alpha: float = 0.05) -> float:
    """Two-sided Bonferroni |t| threshold for n_tests signals."""
    return float(stats.norm.ppf(1 - alpha / (2 * max(n_tests, 1))))

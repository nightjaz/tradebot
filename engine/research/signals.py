"""Price/volume signals and per-day cross-sectional processing.

Every raw signal at row t is a function of panel rows <= t only (tested in tests/test_research.py).
Sign convention: higher value = expected to outperform, per the stated hypothesis.
"""
from __future__ import annotations

import numpy as np
import pandas as pd


def reversal_5d(p: dict) -> pd.DataFrame:
    """Short-term reversal: -(5-day return)."""
    c = p["close"]
    return -(c / c.shift(5) - 1)


def momentum_12_1(p: dict) -> pd.DataFrame:
    """12-month return skipping the most recent month (t-252 .. t-21)."""
    c = p["close"]
    return c.shift(21) / c.shift(252) - 1


def rel_strength_20d(p: dict) -> pd.DataFrame:
    """Stock 20-day return minus NIFTY 200 20-day return.
    Note: subtracting the same index return from every stock does not change cross-sectional ranks,
    so after z-scoring this is the 20-day return itself. Kept to match the original platform signal."""
    c, idx = p["close"], p["index_close"]
    return (c / c.shift(20) - 1).sub(idx / idx.shift(20) - 1, axis=0)


def vwap_deviation_20d(p: dict) -> pd.DataFrame:
    """Price stretched above its 20-day VWAP is expected to revert: -(close / VWAP20 - 1)."""
    typical = (p["high"] + p["low"] + p["close"]) / 3
    vol = p["volume"].where(p["close"].notna())
    vwap = (typical * vol).rolling(20, min_periods=15).sum() / vol.rolling(20, min_periods=15).sum()
    return -(p["close"] / vwap - 1)


def volume_shock(p: dict) -> pd.DataFrame:
    """log(today's volume / average of the previous 20 days). No sign hypothesis; sign set on train data."""
    v = p["volume"].where(p["volume"] > 0)
    return np.log(v / v.shift(1).rolling(20, min_periods=15).mean())


def low_vol_atr(p: dict) -> pd.DataFrame:
    """Low-volatility effect: -(ATR14 / close)."""
    h, l, c = p["high"], p["low"], p["close"]
    prev = c.shift(1)
    tr = np.fmax(np.fmax(h - l, (h - prev).abs()), (l - prev).abs())
    atr = tr.rolling(14, min_periods=10).mean()
    return -(atr / c)


PRICE_SIGNALS = {
    "reversal_5d": reversal_5d,
    "momentum_12_1": momentum_12_1,
    "rel_strength_20d": rel_strength_20d,
    "vwap_dev_20d": vwap_deviation_20d,
    "volume_shock": volume_shock,
    "low_vol_atr": low_vol_atr,
}


def compute_price_signals(panels: dict) -> dict[str, pd.DataFrame]:
    return {name: fn(panels) for name, fn in PRICE_SIGNALS.items()}


# ---------------------------------------------------------------- cross-sectional processing

def winsorize_cs(x: pd.DataFrame, lo: float = 0.01, hi: float = 0.99) -> pd.DataFrame:
    ql = x.quantile(lo, axis=1)
    qh = x.quantile(hi, axis=1)
    return x.clip(lower=ql, upper=qh, axis=0)


def zscore_cs(x: pd.DataFrame) -> pd.DataFrame:
    return x.sub(x.mean(axis=1), axis=0).div(x.std(axis=1).replace(0, np.nan), axis=0)


def sector_neutralize(x: pd.DataFrame, sectors: pd.Series) -> pd.DataFrame:
    """Subtract each sector's same-day mean. Sectors with a single name end up at 0."""
    sec = sectors.reindex(x.columns).fillna("UNKNOWN")
    means = x.T.groupby(sec).transform("mean").T
    return x - means


def process(x: pd.DataFrame, sectors: pd.Series | None = None, min_names: int = 30) -> pd.DataFrame:
    """winsorize 1/99 -> z-score -> (optional) sector demean -> re-z-score. Days with < min_names are NaN."""
    z = zscore_cs(winsorize_cs(x))
    if sectors is not None:
        z = zscore_cs(sector_neutralize(z, sectors))
    z[z.notna().sum(axis=1) < min_names] = np.nan
    return z

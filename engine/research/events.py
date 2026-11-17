"""Earnings-event signals from the quarterly-results CSV (screener.in results + BSE filing timestamps).

Point-in-time rule: an announcement timestamped T (IST) becomes usable on the first trading day
whose 15:30 close is at or after T. After-market filings therefore land on the NEXT trading day,
and we trade them at the open of the day after that. This is conservative (it gives up the first
overnight gap) but cannot leak.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

MARKET_CLOSE = pd.Timedelta(hours=15, minutes=30)
AR_COLS = ["30min-ar_pct", "25min-ar_pct", "20min-ar_pct", "15min-ar_pct", "10min-ar_pct", "5min-ar_pct"]


def _num(s: pd.Series) -> pd.Series:
    return pd.to_numeric(s.astype(str).str.replace(",", "").str.replace("%", "").str.strip(),
                         errors="coerce")


def load_events(path: str | Path) -> pd.DataFrame:
    raw = pd.read_csv(path, low_memory=False)
    ev = pd.DataFrame({
        "symbol": raw["Company Symbol"].astype(str).str.strip().str.upper(),
        "period": pd.to_datetime(raw["Period"], format="%b %Y", errors="coerce") + pd.offsets.MonthEnd(0),
        "timestamp": pd.to_datetime(raw["timestamp"], errors="coerce"),
        "net_profit": _num(raw["Net Profit"]),
        "sales": _num(raw["Sales"]),
    })
    ar = pd.DataFrame({c: pd.to_numeric(raw[c], errors="coerce") for c in AR_COLS if c in raw})
    # longest post-announcement window that was actually collected
    ev["reaction_pct"] = ar.bfill(axis=1).iloc[:, 0] if len(ar.columns) else np.nan
    ev = ev.dropna(subset=["period", "timestamp"]).drop_duplicates(["symbol", "period"], keep="last")
    return ev.sort_values(["symbol", "period"]).reset_index(drop=True)


def seasonal_surprise(ev: pd.DataFrame, col: str, window: int = 8, min_obs: int = 4) -> pd.Series:
    """SUE-style surprise: (x_q - x_{q-4}) / std of the previous `window` seasonal changes.
    The std uses only earlier quarters (shift(1)), so the scale never sees the current print."""
    out = pd.Series(np.nan, index=ev.index)
    for _, g in ev.groupby("symbol"):
        s = g.set_index("period")[col]
        lag = s.reindex(s.index - pd.DateOffset(months=12) + pd.offsets.MonthEnd(0))
        d = pd.Series(s.values - lag.values, index=g.index)
        scale = d.shift(1).rolling(window, min_periods=min_obs).std()
        out.loc[g.index] = (d / scale.replace(0, np.nan)).values
    return out


def yoy_profit_surprise(ev: pd.DataFrame) -> pd.Series:
    """(Net profit_q - Net profit_{q-4}) / Sales_q. Needs one prior-year quarter only, is defined when
    profit changes sign, and is scaled by sales instead of price so it needs no market data."""
    out = pd.Series(np.nan, index=ev.index)
    for _, g in ev.groupby("symbol"):
        s = g.set_index("period")
        lag = s["net_profit"].reindex(s.index - pd.DateOffset(months=12) + pd.offsets.MonthEnd(0))
        sales = s["sales"].where(s["sales"] > 0)
        out.loc[g.index] = ((s["net_profit"].values - lag.values) / sales.values)
    return out.clip(-1, 1)


def signal_date(ts: pd.Series, calendar: pd.DatetimeIndex) -> pd.Series:
    """First trading day whose close (15:30) is >= timestamp."""
    day = ts.dt.normalize()
    after_close = (ts - day) > MARKET_CLOSE
    candidate = day + pd.to_timedelta(after_close.astype(int), unit="D")
    pos = calendar.searchsorted(candidate.values, side="left")
    res = pd.Series(pd.NaT, index=ts.index, dtype="datetime64[ns]")
    ok = pos < len(calendar)
    res[ok] = calendar[pos[ok]]
    return res


def event_panel(ev: pd.DataFrame, value_col: str, calendar: pd.DatetimeIndex, symbols: list[str],
                hold_days: int = 60) -> pd.DataFrame:
    """Spread each event's value forward for `hold_days` trading days from its signal date (PEAD window)."""
    e = ev.dropna(subset=[value_col]).copy()
    e = e[e["symbol"].isin(symbols)]
    e["sdate"] = signal_date(e["timestamp"], calendar)
    e = e.dropna(subset=["sdate"]).sort_values("sdate").drop_duplicates(["sdate", "symbol"], keep="last")
    panel = e.pivot(index="sdate", columns="symbol", values=value_col)
    panel = panel.reindex(index=calendar, columns=symbols)
    return panel.ffill(limit=hold_days - 1)


def compute_event_signals(csv_path: str | Path, calendar: pd.DatetimeIndex, symbols: list[str]) -> dict:
    ev = load_events(csv_path)
    ev["profit_sue"] = seasonal_surprise(ev, "net_profit")
    ev["profit_yoy"] = yoy_profit_surprise(ev)
    return {
        "earnings_sue": event_panel(ev, "profit_sue", calendar, symbols),
        "earnings_yoy": event_panel(ev, "profit_yoy", calendar, symbols),
        "earnings_reaction": event_panel(ev, "reaction_pct", calendar, symbols),
    }, ev

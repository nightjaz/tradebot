"""Daily OHLCV for the NIFTY 200 snapshot, cached in DuckDB, plus data-quality checks."""
from __future__ import annotations

from pathlib import Path

import duckdb
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
UNIVERSE_CSV = ROOT / "config" / "nifty200.csv"
DB_PATH = ROOT / "data" / "research.duckdb"
INDEX_TICKER = "^CNX200"
START = "2014-01-01"  # one extra year so 12-month momentum exists from 2015


def load_universe() -> pd.DataFrame:
    uni = pd.read_csv(UNIVERSE_CSV)
    return uni.rename(columns={"Symbol": "symbol", "Industry": "sector", "Company Name": "name"})[
        ["symbol", "name", "sector"]]


def download_prices(symbols: list[str], start: str = START, end: str | None = None) -> pd.DataFrame:
    import yfinance as yf

    tickers = [f"{s}.NS" for s in symbols] + [INDEX_TICKER]
    raw = yf.download(tickers, start=start, end=end, auto_adjust=True, progress=False,
                      group_by="column", threads=True)
    frames = []
    for field in ["Open", "High", "Low", "Close", "Volume"]:
        f = raw[field].stack(future_stack=True).rename(field.lower())
        frames.append(f)
    long = pd.concat(frames, axis=1).reset_index()
    long.columns = ["date", "ticker", "open", "high", "low", "close", "volume"]
    long["symbol"] = long["ticker"].str.replace(".NS", "", regex=False)
    long.loc[long["ticker"] == INDEX_TICKER, "symbol"] = "NIFTY200"
    long = long.dropna(subset=["close"]).drop(columns="ticker")
    long["date"] = pd.to_datetime(long["date"]).dt.tz_localize(None).dt.normalize()
    return long.sort_values(["symbol", "date"]).reset_index(drop=True)


def get_prices(refresh: bool = False) -> pd.DataFrame:
    """Returns long OHLCV (one row per symbol per day). Downloads once, then reads from DuckDB."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect(str(DB_PATH))
    try:
        have = con.execute("select count(*) from information_schema.tables where table_name='prices'").fetchone()[0]
        if refresh or not have:
            df = download_prices(load_universe()["symbol"].tolist())
            con.execute("create or replace table prices as select * from df")
        return con.execute("select * from prices order by symbol, date").df()
    finally:
        con.close()


def quality_report(prices: pd.DataFrame) -> dict:
    """Missing days, zero-volume days, extreme moves and calendar mismatches."""
    stocks = prices[prices["symbol"] != "NIFTY200"]
    calendar = pd.Index(sorted(stocks["date"].unique()))
    out = {"n_symbols": int(stocks["symbol"].nunique()), "n_days": int(len(calendar)),
           "first_date": str(calendar.min().date()), "last_date": str(calendar.max().date())}
    per = stocks.groupby("symbol")["date"].agg(["min", "count"])
    expected = per["min"].map(lambda d: int((calendar >= d).sum()))
    out["missing_rows_after_listing"] = int((expected - per["count"]).clip(lower=0).sum())
    out["zero_volume_rows"] = int((stocks["volume"] <= 0).sum())
    r = stocks.sort_values(["symbol", "date"]).groupby("symbol")["close"].pct_change()
    out["abs_daily_return_gt_20pct"] = int((r.abs() > 0.20).sum())
    idx_dates = set(prices.loc[prices["symbol"] == "NIFTY200", "date"])
    out["stock_dates_missing_from_index"] = int(len(set(calendar) - idx_dates))
    out["symbols_listed_after_2015"] = int((per["min"] > pd.Timestamp("2015-01-31")).sum())
    return out


def to_panels(prices: pd.DataFrame, min_price: float = 1.0) -> dict[str, pd.DataFrame]:
    """Wide date x symbol panels. Zero-volume / sub-min-price days are set to NaN (untradeable)."""
    stocks = prices[prices["symbol"] != "NIFTY200"].copy()
    bad = (stocks["volume"] <= 0) | (stocks["close"] < min_price)
    stocks.loc[bad, ["open", "high", "low", "close"]] = np.nan
    panels = {f: stocks.pivot(index="date", columns="symbol", values=f).sort_index()
              for f in ["open", "high", "low", "close", "volume"]}
    # drop phantom sessions (vendor rows on exchange holidays where almost nothing traded)
    live = panels["open"].notna().sum(axis=1) >= 0.5 * panels["close"].notna().sum(axis=1).rolling(20, min_periods=1).median()
    panels = {k: v.loc[live] for k, v in panels.items()}
    idx = prices[prices["symbol"] == "NIFTY200"].set_index("date")["close"].sort_index()
    panels["index_close"] = idx.reindex(panels["close"].index).ffill()
    return panels


def forward_returns(open_: pd.DataFrame, horizon: int = 1, delay: int = 0) -> pd.DataFrame:
    """fwd[t] = open[t+1+delay+horizon] / open[t+1+delay] - 1  (signal at t close, trade next open)."""
    entry = open_.shift(-(1 + delay))
    exit_ = open_.shift(-(1 + delay + horizon))
    return exit_ / entry - 1

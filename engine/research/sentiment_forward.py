"""Phase 7: forward-only sentiment test. Run daily (or whenever); it rebuilds the log from scratch.

    python engine/research/sentiment_forward.py [--refresh-prices]

Point-in-time rule: a news item is usable at max(published_at, ingested_at). Our collector often
ingests hours after publication, and using published_at would be lookahead. The item is assigned to
the first trading day whose 15:30 close is at/after that time, then traded at the next open.
Historical sentiment we never collected is NOT backfilled; this is a live forward test only.
"""
from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from research.data import ROOT, forward_returns, get_prices, to_panels  # noqa: E402
from research.events import signal_date  # noqa: E402

DB = ROOT / "data" / "edgesignal.db"
OUT = ROOT / "reports" / "research"


def load_news(db: Path = DB) -> pd.DataFrame:
    con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    rows = con.execute("select symbol, payload from events").fetchall()
    con.close()
    recs = []
    for sym, payload in rows:
        p = json.loads(payload)
        pub = pd.to_datetime(p.get("published_at"), utc=True, errors="coerce")
        ing = pd.to_datetime(p.get("ingested_at"), utc=True, errors="coerce")
        avail = max(t for t in (pub, ing) if pd.notna(t)) if pd.notna(pub) or pd.notna(ing) else pd.NaT
        recs.append({"symbol": sym, "available_at": avail, "sentiment": float(p.get("sentiment", 0.0)),
                     "credibility": float(p.get("credibility", 0.5))})
    df = pd.DataFrame(recs).dropna(subset=["available_at"])
    # to naive IST for the trading calendar
    df["available_at"] = df["available_at"].dt.tz_convert("Asia/Kolkata").dt.tz_localize(None)
    return df


def daily_scores(news: pd.DataFrame, calendar: pd.DatetimeIndex) -> pd.DataFrame:
    news = news.copy()
    news["date"] = signal_date(news["available_at"], calendar)
    news = news.dropna(subset=["date"])
    news["w"] = news["credibility"]
    news["ws"] = news["w"] * news["sentiment"]
    g = news.groupby(["date", "symbol"]).agg(ws=("ws", "sum"), w=("w", "sum"), n=("ws", "size"))
    g["score"] = g["ws"] / g["w"].replace(0, np.nan)
    return g.reset_index()[["date", "symbol", "score", "n"]]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--refresh-prices", action="store_true")
    args = ap.parse_args()
    panels = to_panels(get_prices(refresh=args.refresh_prices))
    cal = panels["open"].index
    fwd = forward_returns(panels["open"])
    fwd_rel = fwd.sub(fwd.mean(axis=1), axis=0)  # relative to the universe average
    s = daily_scores(load_news(), cal)
    s["fwd_ret"] = [fwd.at[d, sym] if sym in fwd.columns else np.nan for d, sym in zip(s["date"], s["symbol"])]
    s["fwd_rel"] = [fwd_rel.at[d, sym] if sym in fwd.columns else np.nan for d, sym in zip(s["date"], s["symbol"])]
    OUT.mkdir(parents=True, exist_ok=True)
    s.to_csv(OUT / "sentiment_forward_log.csv", index=False)
    done = s.dropna(subset=["fwd_rel"])
    nonzero = done[done["score"] != 0]
    pooled = nonzero["score"].corr(nonzero["fwd_rel"], method="spearman") if len(nonzero) > 2 else np.nan
    print(f"news rows -> {len(s)} stock-days ({s['date'].min()} .. {s['date'].max()}); "
          f"{len(done)} with realised next-day return, {len(nonzero)} with non-zero sentiment")
    print(f"pooled rank IC (score vs next-day relative return): {pooled:.4f} - far too few observations to judge; "
          f"keep logging. Prices end {cal[-1].date()}; rerun with --refresh-prices for recent days.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

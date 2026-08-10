# EdgeSignal engine

Research/paper-trading engine for intraday NSE strategies. It uses only information available at the bar timestamp, fills entries on the next bar, models fees and adverse slippage, and stores every event, signal and fill in SQLite.

Run the deterministic demo from the repository root:

```powershell
$env:PYTHONPATH='engine'; python engine/run_demo.py
python -m unittest discover -s engine/tests
```

External data and execution are adapters. Do not connect a live broker until the paper-trading acceptance gate is passed and the broker's current API/algo requirements have been confirmed.

## Reddit connector

Reddit ingestion is OAuth-only and keeps no usernames. Register approved Data API access, then set these variables locally (never commit their values):

```powershell
$env:REDDIT_CLIENT_ID='...'
$env:REDDIT_CLIENT_SECRET='...'
$env:REDDIT_USER_AGENT='windows:edgesignal.research:v0.3 (by /u/your_username)'
python engine/ingest_reddit.py
```

The allowlist and credibility priors are in `config/reddit.json`. Reddit excerpts expire after 14 days. Reddit content is not a model-training dataset; it is a low-trust intraday feature that still requires market-price confirmation.

## Blog connector

Curated RSS/Atom sources are configured in `config/blogs.json`. The connector never scrapes full articles, stores at most a 280-character feed excerpt, rejects stale posts, caps blog credibility below official news, and penalizes promotional language.

```powershell
python engine/ingest_blogs.py
```

## Stock universe

`config/nifty200.csv` is a dated snapshot of the official Nifty 200 constituent file. Regenerate `config/symbol_aliases.json` after refreshing that CSV:

```powershell
python engine/sync_nifty_universe.py
```

The generator requires exactly 200 unique symbols, merges curated brand-name overrides, and avoids plain-text matching for ambiguous tickers such as BSE, IDEA, OIL, and PAGE.

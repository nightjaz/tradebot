# NIFTY 200 cross-sectional signal research

**Question:** do EdgeSignal's price/volume signals predict *next-day relative* returns across NIFTY 200 stocks, after Indian trading costs?

**Short answer:** they predict, but the edge doesn't survive costs. The combined signal has a rank IC of about 0.02–0.03 in every period, including the untouched 2024–2026 test (IC 0.022, t = 5.1). It passes the shuffle and delay tests. Before costs the market-neutral long-short book has a Sharpe of about 1.0–2.0. After STT, stamp duty, exchange fees and 7.5 bps slippage it is negative out of sample (test net Sharpe −0.5; −0.2 averaged over rebalance days). The predictable part is mostly 1–2 day reversal, and capturing it means turning the book over faster than delivery-STT allows.

## Reproduce

```powershell
pip install yfinance duckdb scikit-learn scipy matplotlib pandas
python engine/run_backtest.py                 # all results -> reports/research/
python -m unittest engine/tests/test_research.py
python engine/research/sentiment_forward.py   # Phase 7 forward log
```

The first run downloads prices into `data/research.duckdb` (git-ignored). Add `--refresh-prices` to update them. `--events PATH` points at the quarterly-results CSV (default `~/Downloads/quarterly_results_fixed.csv`).

Outputs: `report.md` (every table), `results.json`, `tearsheet.png`, `daily_pnl.csv`, `test_access_log.csv`.

## Timing (the no-lookahead contract)

* `signal[t]` uses only data available at day *t*'s close.
* `fwd_ret[t] = open[t+2] / open[t+1] − 1`: enter at the next open, exit at the open after that.
* An earnings filing at time T is usable from the first trading day whose 15:30 close is at or after T. A news item is usable at **max(published_at, ingested_at)**. The collector ingested all 155 stored items in one batch on 2026-08-10, so keying on `published_at` would have backdated up to 15 months of news.
* Ridge is retrained every January on an expanding window ending 5 trading days before the test year.

Each of these is a unit test on synthetic data (`engine/tests/test_research.py`). Future rows are perturbed and the past outputs must stay identical. Rewriting test-year labels must not change that year's walk-forward predictions. Perfect foresight must win and noise must not.

## Data

| Source | Used for | Notes |
|---|---|---|
| yfinance `.NS` daily OHLCV, 2014 to today, split/dividend adjusted | price signals, returns | 200 current constituents. 4 vendor rows on exchange holidays removed (zero volume across the universe) |
| `^CNX200` | benchmark, relative strength | |
| `quarterly_results_fixed.csv` | earnings event study | 19.6k filings, but NIFTY 200 names only from **2022**. The 2015–2021 rows are small caps outside the universe. `quat.csv` and `directions.csv` are subsets of it (2021–2025, after-market only) and weren't needed. |
| `data/edgesignal.db` (RSS, blogs, Reddit) | sentiment forward test | forward only, never backfilled |

Data checks are in `report.md`: 11 missing stock-days after listing, 924 zero-volume rows (treated as untradeable), 120 daily moves above 20% (kept: they are real), 54 names listed after Jan 2015.

## Method

1. **Signals** (`signals.py`): 5-day reversal, 12-1 momentum, 20-day relative strength, 20-day VWAP deviation, volume shock, ATR/price low-volatility.
2. **Cross-sectional processing** for each day: winsorize at 1/99%, z-score, subtract the sector mean (NIFTY industry), z-score again.
3. **Evaluation** (`evaluate.py`): daily rank IC, t-stat, ICIR, top-minus-bottom decile spread, IC decay at 1/2/5/10 days, and pairwise signal correlation.
4. **Combination** (`model.py`): equal-weight z-scores with signs taken from **train-period IC**, and walk-forward ridge. Ridge alpha is chosen on validation IC.
5. **Portfolio** (`backtest.py`): long the top 20%, short the bottom 20%, each leg normalised to 1, with a 4% per-name cap (2% of the gross book) and redistribution. Rebalance every 1 or 5 days.
6. **Costs:** the long leg is cash delivery (STT 0.1% each side, stamp 0.015%, exchange and SEBI fees, GST), 18.6 bps per unit traded. The short leg is single-stock futures (STT 0.02% on sells), 9.2 bps per unit traded. Both include 7.5 bps slippage. Overnight cash shorts are not allowed in India.
7. **Selection:** the combiner (EW or ridge) and rebalance frequency (1 or 5 days) are picked by **validation net Sharpe**. The pick was `ridge, rebalance every 5 days`.

Splits: train 2015–2021, validation 2022–2023, test 2024–2026-11.

## Results

| Period | Composite IC (t) | Gross Sharpe | Net Sharpe | Net ann. return | Ann. cost | Net max DD | Corr to NIFTY 200 |
|---|---|---|---|---|---|---|---|
| Train (2017–21)* | 0.033 (10.4) | 2.02 | 0.72 | 9.2% | 16.5% | −15% | 0.08 |
| Validation | 0.020 (4.0) | 0.39 | −0.83 | −10.5% | 15.4% | −23% | 0.05 |
| **Test** | **0.022 (5.1)** | **1.02** | **−0.51** | **−5.4%** | 16.1% | −29% | 0.05 |

\*Ridge needs two years of history, so the book starts in 2017. Returns are on $1 long plus $1 short. One-way turnover is about 12% of the book per day.

**Single signals** (train → validation, sector-neutral IC): 5-day reversal 0.031 → 0.021 and VWAP deviation 0.028 → 0.017 carry most of the edge. Volume shock is reliably negative (−0.013 → −0.010). Relative strength flips toward zero in validation, and its train sign (−) is really short-term reversal again. Momentum is weak in validation (0.004). Low-vol has a positive IC but a negative decile spread: it works in the middle of the distribution, not the tails. Reversal and VWAP decay to near zero by day 5. Momentum and low-vol are flat across horizons but too weak to pay for trading.

### Robustness

* **Shuffle test** (100 within-day permutations of next-day returns): real gross Sharpe 1.41 vs shuffled −0.00 ± 0.34, IC 0.0001, p ≈ 0.01. No mechanical leak.
* **Delay:** gross Sharpe in train goes 2.02 → 1.70 → 1.30 → 0.27 for 0, 1, 2 and 5 extra days. It decays smoothly, as a real short-horizon signal should.
* **Costs:** net Sharpe at 0×, 1×, 2× costs is 2.02 / 0.72 / −0.55 in train and 1.02 / −0.51 / −1.93 in test. The edge disappears at roughly base cost.
* **Rebalance day:** with 5-day rebalancing, the choice of starting day swings test gross Sharpe from 0.90 to 1.72 and net from −0.56 to +0.24. Any single-run number carries roughly ±0.4 Sharpe of this noise.
* **By year:** gross Sharpe is positive in 9 of 10 years, and 2023 is the exception (−0.18). Net is positive only in 2017–2020 and 2024.
* **2020 crash** (15 Feb–30 Apr): strategy +11.8% gross, +9.0% net, vs NIFTY 200 −22.9%.
* **F&O-eligible proxy** (top 140 by trailing traded value, standing in for the actual F&O list, which isn't stored): similar, test gross 1.15 and net −0.20.

### Earnings event study (separate, not in the composite)

There is no NIFTY 200 history before 2022, so these signals can't be trained. Their sign is fixed in advance (+) and they are reported for validation and test only.

| Signal | Validation IC (t) | Test IC (t) |
|---|---|---|
| Post-filing 30-min price reaction, held 60 days | 0.008 (1.3) | 0.013 (2.8) |
| YoY net-profit change / sales | 0.017 (1.1) | −0.002 (−0.4) |
| SUE (needs 2 years of history, exists from 2024 only) | n/a | −0.005 (−0.9) |

The reaction signal is the only promising one: test t = 2.8. That falls just short of the multiple-testing bar (|t| > 2.97), so it is a lead, not a result.

## Signal and decision log (everything tried)

| # | Item | Outcome |
|---|---|---|
| 1–6 | Six price signals | All reported above; none dropped after looking |
| 7 | Earnings SUE (8-quarter scale) | Kept but nearly empty: coverage starts 2022, so it exists only from 2024 |
| 8 | YoY profit / sales | Added after seeing #7 was empty (coverage, not performance). Weak |
| 9 | Earnings price reaction | Weak in validation, t 2.8 in test |
| — | 4 ridge alphas | Picked by validation IC (alpha = 1; all within 0.001) |
| — | 2 combiners × 2 rebalance frequencies | Picked on validation |
| — | Sector-neutral vs raw | Both reported. Sector-neutral is used throughout (decided in advance) |

Total: 9 signals plus 8 model choices. Bonferroni |t| threshold 2.97. The composite's test t of 5.1 clears it; its net Sharpe does not.

**Test-set honesty:** `test_access_log.csv` records every run that produced test numbers. Six runs happened during development. The selection rule (validation net Sharpe) and the signal set were fixed before the first one. Changes after that were bug fixes, not tuning:

* stop counting pre-model days as zero-return days;
* move the earnings signals out of the composite once coverage showed no train data;
* remove vendor rows on exchange holidays.

The last fix changed the test numbers (net −0.12 → −0.51), almost entirely by shifting the 5-day rebalance calendar. That is why the rebalance-day check exists.

## Limitations

* **Survivorship bias:** only today's constituents are used, so names that dropped out (often after falling) are missing. This most likely *flatters* the long side and momentum, and *hurts* a short-reversal book less. No historical NIFTY 200 membership file is stored, so the size of the bias isn't measured. That is the first thing to fix.
* The short leg assumes futures exist for every short name, at cash-price returns, with no basis or roll costs. Half the universe isn't F&O-eligible on any given date.
* Open prices from Yahoo are auction prices, and real fills at the open in mid-caps will be worse than 7.5 bps on some days.
* No LightGBM. sklearn ridge only, and the ridge coefficients are close to equal-weight anyway.
* The relative-strength signal is rank-identical to the plain 20-day return (subtracting the index return doesn't change ranks).

## What would make it tradable

The IC is real. The problem is cost per unit of IC. Things to try next, all on train/validation:

* trade only when the forecast change exceeds a cost hurdle (a no-trade band);
* use the reversal signal as an *entry-timing* overlay on a slow book (momentum, low-vol, earnings reaction) instead of as a standalone daily book;
* intraday execution of the reversal leg, which avoids delivery STT entirely. The existing EdgeSignal intraday engine already models those costs.

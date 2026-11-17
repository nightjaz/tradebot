# NIFTY 200 cross-sectional signal research — results

Generated 2026-11-18T02:38:19. Chosen configuration (picked on validation): **ridge|rebalance=5**.

## Strategy summary

| Period | IC mean | IC t | Gross Sharpe | Net Sharpe | Net ann. ret | Ann. cost | Max DD (net) | Turnover/day | Corr NIFTY200 |
|---|---|---|---|---|---|---|---|---|---|
| train | 0.0330 | 10.41 | 2.02 | 0.72 | 0.092 | 0.165 | -0.153 | 0.12 | 0.08 |
| validation | 0.0199 | 3.98 | 0.39 | -0.83 | -0.105 | 0.154 | -0.234 | 0.11 | 0.05 |
| test | 0.0224 | 5.13 | 1.02 | -0.51 | -0.054 | 0.161 | -0.292 | 0.12 | 0.05 |

## Single signals (sector-neutral rank IC vs next-day open-to-open return)

9 signals; Bonferroni |t| threshold across all signals + model choices: 2.97.

| Signal | Sign | Train IC | Train t | Train ICIR | Val IC | Val t | Raw (no sector-neutral) train IC | Top-bottom decile bps/day (train) | L/S gross Sharpe train / val |
|---|---|---|---|---|---|---|---|---|---|
| reversal_5d | +1 | 0.0310 | 11.68 | 4.46 | 0.0210 | 4.22 | 0.0278 | 12.6 | 2.34 / 0.82 |
| momentum_12_1 | +1 | 0.0138 | 4.79 | 1.83 | 0.0040 | 0.77 | 0.0167 | 7.9 | 1.03 / 1.03 |
| rel_strength_20d | -1 | -0.0225 | -8.41 | -3.21 | -0.0073 | -1.45 | -0.0167 | -11.4 | 1.79 / -0.08 |
| vwap_dev_20d | +1 | 0.0276 | 9.95 | 3.80 | 0.0172 | 3.31 | 0.0216 | 16.0 | 2.25 / 0.94 |
| volume_shock | -1 | -0.0131 | -5.95 | -2.27 | -0.0100 | -2.77 | -0.0148 | -3.7 | 0.69 / 0.28 |
| low_vol_atr | +1 | 0.0164 | 4.93 | 1.88 | 0.0135 | 2.24 | 0.0199 | -0.6 | -0.42 / -1.71 |

IC decay (train, IC vs single-day return k days ahead):

| Signal | k=1 | k=2 | k=5 | k=10 |
|---|---|---|---|---|
| reversal_5d | 0.0310 | 0.0192 | 0.0071 | 0.0032 |
| momentum_12_1 | 0.0138 | 0.0140 | 0.0140 | 0.0135 |
| rel_strength_20d | -0.0225 | -0.0150 | -0.0082 | -0.0037 |
| vwap_dev_20d | 0.0276 | 0.0160 | 0.0063 | 0.0021 |
| volume_shock | -0.0131 | -0.0057 | -0.0013 | 0.0017 |
| low_vol_atr | 0.0164 | 0.0156 | 0.0156 | 0.0147 |

## Leakage and robustness

**Shuffle test** (100 within-day permutations of next-day returns): real gross Sharpe 1.41; shuffled mean -0.00, 95th pct 0.63, shuffled IC 0.0001, p ≈ 0.010.

**Delay test** (gross Sharpe when trading d extra days late):

| Extra delay | train | validation | test |
|---|---|---|---|
| 0 | 2.02 | 0.39 | 1.02 |
| 1 | 1.70 | -0.08 | 0.51 |
| 2 | 1.30 | -0.48 | 0.82 |
| 5 | 0.27 | -0.53 | 0.49 |

**Rebalance-day sensitivity** (Sharpe across every possible starting day of the rebalance cycle):

| Period | Gross mean [min, max] | Net mean [min, max] |
|---|---|---|
| train | 1.81 [1.52, 2.02] | 0.52 [0.22, 0.72] |
| validation | 0.37 [-0.26, 0.77] | -0.88 [-1.51, -0.53] |
| test | 1.29 [0.90, 1.72] | -0.19 [-0.56, 0.24] |

**Cost sensitivity** (net Sharpe at k× base costs):

| Cost × | train | validation | test |
|---|---|---|---|
| 0.0 | 2.02 | 0.39 | 1.02 |
| 1.0 | 0.72 | -0.83 | -0.51 |
| 2.0 | -0.55 | -2.00 | -1.93 |
| 3.0 | -1.70 | -3.03 | -3.14 |
| 5.0 | -3.50 | -4.63 | -4.85 |

**By year:**

| Year | IC | Gross Sharpe | Net Sharpe | Gross ret | Net ret |
|---|---|---|---|---|---|
| 2015 | n/a | n/a | n/a | 0.000 | 0.000 |
| 2016 | n/a | n/a | n/a | 0.000 | 0.000 |
| 2017 | 0.0389 | 2.28 | 0.37 | 0.201 | 0.033 |
| 2018 | 0.0356 | 3.53 | 1.94 | 0.388 | 0.214 |
| 2019 | 0.0350 | 3.28 | 1.75 | 0.341 | 0.184 |
| 2020 | 0.0255 | 1.34 | 0.50 | 0.247 | 0.093 |
| 2021 | 0.0303 | 0.70 | -0.60 | 0.082 | -0.072 |
| 2022 | 0.0193 | 0.93 | -0.25 | 0.117 | -0.032 |
| 2023 | 0.0204 | -0.18 | -1.44 | -0.022 | -0.174 |
| 2024 | 0.0225 | 1.41 | 0.05 | 0.162 | 0.006 |
| 2025 | 0.0248 | 1.15 | -0.36 | 0.119 | -0.038 |
| 2026 | 0.0195 | 0.28 | -1.57 | 0.021 | -0.120 |

**2020 crash (15 Feb – 30 Apr 2020):** strategy gross 0.118, net 0.090, NIFTY 200 -0.229.

**F&O-eligible proxy universe** (top 140 by trailing 60-day median traded value):

| Period | Gross Sharpe | Net Sharpe |
|---|---|---|
| train | 1.64 | 0.43 |
| validation | 0.70 | -0.46 |
| test | 1.15 | -0.20 |

## Earnings event study (not in the composite; sign fixed a priori = +1)

Source: quarterly results CSV. NIFTY 200 coverage starts 2022, so there is no train period. Values are held for 60 trading days after the first close at/after the filing timestamp.

| Signal | Period | IC | t | Median live names | Decile spread bps/day | L/S gross Sharpe |
|---|---|---|---|---|---|---|
| earnings_sue | validation | n/a | n/a | 0 | n/a | n/a |
| earnings_sue | test | -0.0053 | -0.85 | 146 | -0.4 | 0.01 |
| earnings_yoy | validation | 0.0168 | 1.11 | 116 | 12.5 | -1.96 |
| earnings_yoy | test | -0.0018 | -0.41 | 144 | 2.0 | 0.62 |
| earnings_reaction | validation | 0.0079 | 1.31 | 95 | 6.7 | -0.00 |
| earnings_reaction | test | 0.0132 | 2.83 | 97 | 1.9 | 1.00 |

## Model selection (validation only)

| Candidate | Val gross Sharpe | Val net Sharpe |
|---|---|---|
| equal_weight|rebalance=1 | 0.11 | -3.27 |
| equal_weight|rebalance=5 | -0.04 | -1.33 |
| ridge|rebalance=1 | 0.70 | -2.07 |
| ridge|rebalance=5 | 0.39 | -0.83 |

Ridge alpha by validation IC: 1: 0.0199, 1000: 0.0199, 100000: 0.0196, 1e+07: 0.0190

Costs per unit traded: long leg (cash delivery) 18.6 bps, short leg (stock futures) 9.2 bps, incl. 7.5 bps slippage.

## Data quality

```
{
  "n_symbols": 200,
  "n_days": 3175,
  "first_date": "2014-01-01",
  "last_date": "2026-11-16",
  "missing_rows_after_listing": 11,
  "zero_volume_rows": 924,
  "abs_daily_return_gt_20pct": 120,
  "stock_dates_missing_from_index": 7,
  "symbols_listed_after_2015": 54
}
{
  "file": "quarterly_results_fixed.csv",
  "rows": 19609,
  "rows_in_universe": 2094,
  "symbols_in_universe": 179,
  "first": "2015-07-31 17:46:42",
  "last": "2025-10-25 15:57:01"
}
```

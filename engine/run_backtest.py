"""One command reproduces every number in reports/research/:

    python engine/run_backtest.py [--refresh-prices] [--events PATH] [--shuffles 20]

Question: do these signals predict next-day relative returns across NIFTY 200 stocks, after costs?
Splits: train 2015-2021, validation 2022-2023, test 2024-today. Every design choice (signal signs,
ridge alpha, combiner, rebalance frequency) is made on train/validation; test is reported, never tuned.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from research import backtest as bt  # noqa: E402
from research import evaluate as ev  # noqa: E402
from research.data import ROOT, forward_returns, get_prices, load_universe, quality_report, to_panels  # noqa: E402
from research.events import compute_event_signals  # noqa: E402
from research.model import equal_weight, walk_forward_ridge  # noqa: E402
from research.signals import compute_price_signals, process  # noqa: E402

PERIODS = {"train": ("2015-01-01", "2021-12-31"), "validation": ("2022-01-01", "2023-12-31"),
           "test": ("2024-01-01", "2099-12-31")}
DEFAULT_EVENTS = Path.home() / "Downloads" / "quarterly_results_fixed.csv"
OUT = ROOT / "reports" / "research"
RIDGE_ALPHAS = [1.0, 1e3, 1e5, 1e7]


def slice_(x, period):
    a, b = PERIODS[period]
    return x.loc[a:b]


def per_period(fn, x) -> dict:
    return {p: fn(slice_(x, p)) for p in PERIODS}


def shuffle_within_day(df: pd.DataFrame, rng) -> pd.DataFrame:
    arr = df.to_numpy(copy=True)
    for row in arr:
        rng.shuffle(row)
    return pd.DataFrame(arr, index=df.index, columns=df.columns)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--refresh-prices", action="store_true")
    ap.add_argument("--events", default=str(DEFAULT_EVENTS))
    ap.add_argument("--shuffles", type=int, default=100)
    args = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    log = lambda *a: print(f"[{datetime.now():%H:%M:%S}]", *a, flush=True)  # noqa: E731

    # ---------------------------------------------------------------- Phase 1: data
    prices = get_prices(refresh=args.refresh_prices)
    quality = quality_report(prices)
    panels = to_panels(prices)
    open_ = panels["open"]
    dates, symbols = open_.index, list(open_.columns)
    fwd = forward_returns(open_)
    idx = panels["index_close"]
    bench = idx.shift(-2) / idx.shift(-1) - 1  # index move over (roughly) the same holding window
    sectors = load_universe().set_index("symbol")["sector"]
    log("prices", quality)

    # ---------------------------------------------------------------- Phase 2: signals
    raw = compute_price_signals(panels)
    event_path = Path(args.events)
    event_info, ev_sigs = {}, {}
    if event_path.exists():
        ev_sigs, events = compute_event_signals(event_path, dates, symbols)
        in_uni = events[events["symbol"].isin(symbols)]
        event_info = {"file": event_path.name, "rows": len(events), "rows_in_universe": len(in_uni),
                      "symbols_in_universe": int(in_uni["symbol"].nunique()),
                      "first": str(events["timestamp"].min()), "last": str(events["timestamp"].max())}
    else:
        log(f"events file not found ({event_path}); running price signals only")
    z = {k: process(v, sectors) for k, v in raw.items()}
    z_raw = {k: process(v, None) for k, v in raw.items()}
    start = pd.Timestamp("2015-01-01")
    z = {k: v.loc[start:] for k, v in z.items()}
    z_raw = {k: v.loc[start:] for k, v in z_raw.items()}
    fwd_s = fwd.loc[start:]
    # Earnings data only covers NIFTY 200 names from 2022, so these can't be trained on. Their sign is fixed
    # a priori (good news / positive reaction -> drift up) and they are reported as a separate event study.
    ez = {k: process(v, sectors, min_names=20).loc[start:] for k, v in ev_sigs.items()}
    log("signals", list(z), "event signals", list(ez))

    # ---------------------------------------------------------------- Phase 3: single-signal evaluation
    single, ics = {}, {}
    for name, sig in z.items():
        ic = ev.daily_ic(sig, fwd_s)
        ics[name] = ic
        single[name] = {
            "sector_neutral": {p: ev.ic_summary(slice_(ic, p)) for p in ["train", "validation"]},
            "raw": {p: ev.ic_summary(slice_(ev.daily_ic(z_raw[name], fwd_s), p)) for p in ["train", "validation"]},
            "decile_spread_bps_train": float(slice_(ev.quantile_spread(sig, fwd_s), "train").mean() * 1e4),
            "decay_train": {str(k): float(v) for k, v in
                            ev.ic_decay(slice_(sig, "train"), open_.loc[start:]).items()},
        }
    corr = ev.signal_correlation({k: slice_(v, "train") for k, v in z.items()})
    log("single-signal IC done")

    # ---------------------------------------------------------------- Phase 4: combine (choices on train only)
    signs = {k: float(np.sign(single[k]["sector_neutral"]["train"]["ic_mean"]) or 1.0) for k in z}
    composite_ew = equal_weight(z, signs)

    ridge_val = {}
    ridge_preds = {}
    for a in RIDGE_ALPHAS:
        p, coefs = walk_forward_ridge(z, fwd_s, alpha=a, first_test_year=2017, last_year=dates[-1].year)
        ridge_preds[a] = (p, coefs)
        ridge_val[a] = ev.ic_summary(slice_(ev.daily_ic(p, fwd_s), "validation"))["ic_mean"]
    best_alpha = max(ridge_val, key=lambda a: ridge_val[a])
    composite_ridge, ridge_coefs = ridge_preds[best_alpha]
    log("ridge alpha (by validation IC)", best_alpha, ridge_val)

    # ---------------------------------------------------------------- Phase 5: portfolio + backtest
    tradeable = open_.shift(-1).notna() & open_.shift(-2).notna()  # can enter and exit
    tradeable = tradeable.loc[start:]
    traded_value = (panels["close"] * panels["volume"]).rolling(60, min_periods=40).median()
    fno_proxy = traded_value.rank(axis=1, ascending=False).le(140).loc[start:]
    base_costs = bt.CostModel()

    def backtest(score, rebalance=1, costs=base_costs, universe=None, ret=fwd_s, offset=0):
        t = tradeable if universe is None else tradeable & universe
        w = bt.build_weights(score, t, rebalance_every=rebalance, offset=offset)
        return bt.run(w, ret, costs), w

    candidates = {}
    for cname, score in {"equal_weight": composite_ew, "ridge": composite_ridge}.items():
        for reb in (1, 5):
            res, _ = backtest(score, reb)
            v = slice_(res, "validation")
            candidates[f"{cname}|rebalance={reb}"] = {
                "val_net_sharpe": bt.metrics(v["net"]).get("sharpe", np.nan),
                "val_gross_sharpe": bt.metrics(v["gross"]).get("sharpe", np.nan)}
    chosen = max(candidates, key=lambda k: candidates[k]["val_net_sharpe"])
    cname, reb = chosen.split("|")[0], int(chosen.split("=")[1])
    score = composite_ew if cname == "equal_weight" else composite_ridge
    log("chosen on validation:", chosen, candidates)

    res, weights = backtest(score, reb)
    summary = {}
    for p in PERIODS:
        r = slice_(res, p)
        summary[p] = {"gross": bt.metrics(r["gross"], r["turnover"], benchmark=bench),
                      "net": bt.metrics(r["net"], r["turnover"], r["cost"], benchmark=bench),
                      "composite_ic": ev.ic_summary(slice_(ev.daily_ic(score, fwd_s), p))}
    # every individual signal as its own long-short portfolio (gross), to see where the edge comes from
    per_signal_bt = {}
    for name in z:
        r1, _ = backtest(z[name].mul(signs[name]), 1)
        per_signal_bt[name] = {p: bt.metrics(slice_(r1["gross"], p)).get("sharpe", np.nan)
                               for p in ["train", "validation"]}

    # ---------------------------------------------------------------- Phase 6: leakage + robustness
    rng = np.random.default_rng(7)
    shuf_sh, shuf_ic = [], []
    for _ in range(args.shuffles):
        f_sh = shuffle_within_day(fwd_s, rng)
        rr, _ = backtest(score, reb, ret=f_sh)
        shuf_sh.append(bt.metrics(rr["gross"])["sharpe"])
        shuf_ic.append(ev.daily_ic(score, f_sh).mean())
    real_sh = bt.metrics(res["gross"])["sharpe"]
    robustness = {
        "shuffle_test": {"n": args.shuffles, "real_gross_sharpe_all": real_sh,
                         "shuffled_gross_sharpe_mean": float(np.mean(shuf_sh)),
                         "shuffled_gross_sharpe_sd": float(np.std(shuf_sh)),
                         "shuffled_gross_sharpe_p95": float(np.percentile(shuf_sh, 95)),
                         "shuffled_ic_mean": float(np.mean(shuf_ic)),
                         "p_value": float((np.sum(np.array(shuf_sh) >= real_sh) + 1) / (len(shuf_sh) + 1))},
        "delay_test": {}, "cost_sensitivity": {}, "by_year": {}, "fno_proxy_universe": {}, "crash_2020": {},
    }
    for d in (0, 1, 2, 5):
        rr, _ = backtest(score, reb, ret=forward_returns(open_, 1, delay=d).loc[start:])
        robustness["delay_test"][d] = {p: bt.metrics(slice_(rr["gross"], p)).get("sharpe") for p in PERIODS}
    for m in (0.0, 1.0, 2.0, 3.0, 5.0):
        rr, _ = backtest(score, reb, costs=bt.CostModel(multiplier=m))
        robustness["cost_sensitivity"][m] = {p: bt.metrics(slice_(rr["net"], p)).get("sharpe") for p in PERIODS}
    comp_ic_year = ev.daily_ic(score, fwd_s).groupby(lambda d: d.year).mean()
    for y, g in res.groupby(res.index.year):
        robustness["by_year"][int(y)] = {"gross_sharpe": bt.metrics(g["gross"]).get("sharpe"),
                                         "net_sharpe": bt.metrics(g["net"]).get("sharpe"),
                                         "gross_return": float(g["gross"].sum()),
                                         "net_return": float(g["net"].sum()),
                                         "composite_ic": float(comp_ic_year.get(y, np.nan))}
    crash = res.loc["2020-02-15":"2020-04-30"]
    robustness["crash_2020"] = {"gross_return": float(crash["gross"].sum()), "net_return": float(crash["net"].sum()),
                                "nifty200_return": float(bench.loc["2020-02-15":"2020-04-30"].sum())}
    phase = {p: {"gross": [], "net": []} for p in PERIODS}
    for off in range(reb):
        rr, _ = backtest(score, reb, offset=off)
        for p in PERIODS:
            phase[p]["gross"].append(bt.metrics(slice_(rr["gross"], p)).get("sharpe"))
            phase[p]["net"].append(bt.metrics(slice_(rr["net"], p)).get("sharpe"))
    robustness["rebalance_phase"] = {p: {k: {"mean": float(np.mean(v)), "min": float(np.min(v)), "max": float(np.max(v))}
                                         for k, v in d.items()} for p, d in phase.items()}
    rr, _ = backtest(score, reb, universe=fno_proxy)
    robustness["fno_proxy_universe"] = {p: {"gross": bt.metrics(slice_(rr["gross"], p)).get("sharpe"),
                                            "net": bt.metrics(slice_(rr["net"], p)).get("sharpe")} for p in PERIODS}
    log("robustness done")

    # ---------------------------------------------------------------- earnings event study (val + test only)
    event_study = {}
    for name, sig in ez.items():
        ic = ev.daily_ic(sig, fwd_s, min_names=20)
        live = sig.notna().sum(axis=1)
        r1 = bt.run(bt.build_weights(sig, tradeable), fwd_s, base_costs)
        event_study[name] = {p: {**ev.ic_summary(slice_(ic, p)),
                                 "median_live_names": float(slice_(live[live > 0], p).median()) if (slice_(live, p) > 0).any() else 0.0,
                                 "decile_spread_bps": float(slice_(ev.quantile_spread(sig, fwd_s, min_names=20), p).mean() * 1e4),
                                 "ls_gross_sharpe": bt.metrics(slice_(r1["gross"], p)).get("sharpe")}
                             for p in ["validation", "test"]}
        event_study[name]["decay_all"] = {str(k): float(v) for k, v in ev.ic_decay(sig, open_.loc[start:]).items()}

    # ---------------------------------------------------------------- outputs
    results = {"generated": datetime.now().isoformat(timespec="seconds"), "data_quality": quality,
               "events": event_info, "periods": PERIODS, "signals_tried": len(z) + len(ez),
               "bonferroni_t_threshold": ev.multiple_testing_threshold(
                   len(z) + len(ez) + len(candidates) + len(RIDGE_ALPHAS)),
               "signs_from_train": signs, "single_signal": single, "single_signal_ls_sharpe": per_signal_bt,
               "signal_correlation_train": corr.round(3).to_dict(),
               "ridge": {"alpha_validation_ic": ridge_val, "chosen_alpha": best_alpha,
                         "coefs_by_year": ridge_coefs},
               "candidates_validation": candidates, "chosen": chosen,
               "costs_bps_per_unit_traded": {"long_leg_delivery": base_costs.long_bps(),
                                             "short_leg_futures": base_costs.short_bps()},
               "summary": summary, "robustness": robustness, "event_study": event_study}
    (OUT / "results.json").write_text(json.dumps(results, indent=2, default=_jsonable), encoding="utf-8")
    res.to_csv(OUT / "daily_pnl.csv")
    _test_access_log(results)
    _tearsheet(res, ics, score, fwd_s, open_.loc[start:], OUT / "tearsheet.png")
    (OUT / "report.md").write_text(_report(results), encoding="utf-8")
    log("wrote", OUT)
    return 0


def _jsonable(o):
    if isinstance(o, (np.floating, np.integer)):
        return o.item()
    if isinstance(o, pd.Timestamp):
        return str(o)
    return str(o)


def _test_access_log(results):
    """Every run that prints test numbers is appended here, so 'how often did you look at test?' has an answer."""
    cfg = json.dumps({k: results[k] for k in ["chosen", "signs_from_train", "periods"]}, sort_keys=True, default=str)
    line = f"{results['generated']},{hashlib.sha1(cfg.encode()).hexdigest()[:10]},{results['chosen']}," \
           f"{results['summary']['test']['net'].get('sharpe')}\n"
    path = OUT / "test_access_log.csv"
    if not path.exists():
        path.write_text("timestamp,config_hash,chosen,test_net_sharpe\n", encoding="utf-8")
    with path.open("a", encoding="utf-8") as fh:
        fh.write(line)


def _tearsheet(res, ics, score, fwd, open_, path):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(3, 2, figsize=(13, 11))
    eq_g, eq_n = res["gross"].cumsum(), res["net"].cumsum()
    a = ax[0, 0]
    a.plot(eq_g.index, eq_g, label="gross", color="#2a6fdb")
    a.plot(eq_n.index, eq_n, label="net of costs", color="#d9534f")
    for p, (s, _) in PERIODS.items():
        a.axvline(pd.Timestamp(s), color="grey", lw=0.6, ls="--")
        a.text(pd.Timestamp(s), a.get_ylim()[1], f" {p}", va="top", fontsize=8, color="grey")
    a.set_title("Cumulative return (sum of daily L/S returns)")
    a.legend()
    dd = eq_n - eq_n.cummax()
    ax[0, 1].fill_between(dd.index, dd, 0, color="#d9534f", alpha=0.5)
    ax[0, 1].set_title("Drawdown (net)")
    roll = res["net"].rolling(126).mean() / res["net"].rolling(126).std() * np.sqrt(252)
    roll_g = res["gross"].rolling(126).mean() / res["gross"].rolling(126).std() * np.sqrt(252)
    ax[1, 0].plot(roll_g.index, roll_g, color="#2a6fdb", lw=0.8, label="gross")
    ax[1, 0].plot(roll.index, roll, color="#d9534f", lw=0.8, label="net")
    ax[1, 0].axhline(0, color="k", lw=0.5)
    ax[1, 0].set_title("Rolling 6-month Sharpe")
    ax[1, 0].legend()
    cic = ev.daily_ic(score, fwd)
    by_y = cic.groupby(cic.index.year).mean()
    ax[1, 1].bar(by_y.index.astype(str), by_y.values, color=["#2a6fdb" if v > 0 else "#d9534f" for v in by_y])
    ax[1, 1].axhline(0, color="k", lw=0.5)
    ax[1, 1].set_title("Composite rank IC by year")
    ic_tab = pd.DataFrame({k: v.groupby(v.index.year).mean() for k, v in ics.items()})
    im = ax[2, 0].imshow(ic_tab.T.values, cmap="RdBu", vmin=-0.05, vmax=0.05, aspect="auto")
    ax[2, 0].set_yticks(range(len(ic_tab.columns)), ic_tab.columns, fontsize=8)
    ax[2, 0].set_xticks(range(len(ic_tab.index)), ic_tab.index, fontsize=7, rotation=45)
    ax[2, 0].set_title("Single-signal IC by year (sector-neutral)")
    fig.colorbar(im, ax=ax[2, 0], fraction=0.03)
    lags = (1, 2, 5, 10)
    decay = ev.ic_decay(score, open_, lags)
    ax[2, 1].bar([str(l) for l in lags], [decay[l] for l in lags], color="#2a6fdb")
    ax[2, 1].set_title("Composite IC decay (IC vs return k days ahead)")
    ax[2, 1].axhline(0, color="k", lw=0.5)
    fig.tight_layout()
    fig.savefig(path, dpi=110)
    plt.close(fig)


def _f(x, nd=3):
    return "n/a" if x is None or (isinstance(x, float) and np.isnan(x)) else f"{x:.{nd}f}"


def _report(r) -> str:
    L = ["# NIFTY 200 cross-sectional signal research — results", "",
         f"Generated {r['generated']}. Chosen configuration (picked on validation): **{r['chosen']}**.", "",
         "## Strategy summary", "",
         "| Period | IC mean | IC t | Gross Sharpe | Net Sharpe | Net ann. ret | Ann. cost | Max DD (net) | Turnover/day | Corr NIFTY200 |",
         "|---|---|---|---|---|---|---|---|---|---|"]
    for p, s in r["summary"].items():
        g, n, ic = s["gross"], s["net"], s["composite_ic"]
        L.append(f"| {p} | {_f(ic['ic_mean'], 4)} | {_f(ic['t_stat'], 2)} | {_f(g.get('sharpe'), 2)} | "
                 f"{_f(n.get('sharpe'), 2)} | {_f(n.get('ann_return'))} | {_f(n.get('ann_cost'))} | "
                 f"{_f(n.get('max_drawdown'))} | {_f(n.get('avg_daily_turnover'), 2)} | {_f(n.get('corr_to_nifty200'), 2)} |")
    L += ["", "## Single signals (sector-neutral rank IC vs next-day open-to-open return)", "",
          f"{r['signals_tried']} signals; Bonferroni |t| threshold across all signals + model choices: "
          f"{r['bonferroni_t_threshold']:.2f}.", "",
          "| Signal | Sign | Train IC | Train t | Train ICIR | Val IC | Val t | Raw (no sector-neutral) train IC | Top-bottom decile bps/day (train) | L/S gross Sharpe train / val |",
          "|---|---|---|---|---|---|---|---|---|---|"]
    for k, s in r["single_signal"].items():
        tr, va = s["sector_neutral"]["train"], s["sector_neutral"]["validation"]
        ls = r["single_signal_ls_sharpe"][k]
        L.append(f"| {k} | {r['signs_from_train'][k]:+.0f} | {_f(tr['ic_mean'], 4)} | {_f(tr['t_stat'], 2)} | "
                 f"{_f(tr['icir_ann'], 2)} | {_f(va['ic_mean'], 4)} | {_f(va['t_stat'], 2)} | "
                 f"{_f(s['raw']['train']['ic_mean'], 4)} | {_f(s['decile_spread_bps_train'], 1)} | "
                 f"{_f(ls['train'], 2)} / {_f(ls['validation'], 2)} |")
    L += ["", "IC decay (train, IC vs single-day return k days ahead):", "",
          "| Signal | k=1 | k=2 | k=5 | k=10 |", "|---|---|---|---|---|"]
    for k, s in r["single_signal"].items():
        d = s["decay_train"]
        L.append(f"| {k} | " + " | ".join(_f(d[x], 4) for x in ["1", "2", "5", "10"]) + " |")
    rb = r["robustness"]
    sh = rb["shuffle_test"]
    L += ["", "## Leakage and robustness", "",
          f"**Shuffle test** ({sh['n']} within-day permutations of next-day returns): real gross Sharpe "
          f"{_f(sh['real_gross_sharpe_all'], 2)}; shuffled mean {_f(sh['shuffled_gross_sharpe_mean'], 2)}, "
          f"95th pct {_f(sh['shuffled_gross_sharpe_p95'], 2)}, shuffled IC {_f(sh['shuffled_ic_mean'], 4)}, "
          f"p ≈ {_f(sh['p_value'], 3)}.", "",
          "**Delay test** (gross Sharpe when trading d extra days late):", "",
          "| Extra delay | train | validation | test |", "|---|---|---|---|"]
    for d, v in rb["delay_test"].items():
        L.append(f"| {d} | {_f(v['train'], 2)} | {_f(v['validation'], 2)} | {_f(v['test'], 2)} |")
    if rb.get("rebalance_phase"):
        L += ["", "**Rebalance-day sensitivity** (Sharpe across every possible starting day of the rebalance cycle):", "",
              "| Period | Gross mean [min, max] | Net mean [min, max] |", "|---|---|---|"]
        for p, v in rb["rebalance_phase"].items():
            g, n = v["gross"], v["net"]
            L.append(f"| {p} | {_f(g['mean'], 2)} [{_f(g['min'], 2)}, {_f(g['max'], 2)}] | "
                     f"{_f(n['mean'], 2)} [{_f(n['min'], 2)}, {_f(n['max'], 2)}] |")
    L += ["", "**Cost sensitivity** (net Sharpe at k× base costs):", "",
          "| Cost × | train | validation | test |", "|---|---|---|---|"]
    for m, v in rb["cost_sensitivity"].items():
        L.append(f"| {m} | {_f(v['train'], 2)} | {_f(v['validation'], 2)} | {_f(v['test'], 2)} |")
    L += ["", "**By year:**", "", "| Year | IC | Gross Sharpe | Net Sharpe | Gross ret | Net ret |",
          "|---|---|---|---|---|---|"]
    for y, v in rb["by_year"].items():
        L.append(f"| {y} | {_f(v['composite_ic'], 4)} | {_f(v['gross_sharpe'], 2)} | {_f(v['net_sharpe'], 2)} | "
                 f"{_f(v['gross_return'])} | {_f(v['net_return'])} |")
    c = rb["crash_2020"]
    L += ["", f"**2020 crash (15 Feb – 30 Apr 2020):** strategy gross {_f(c['gross_return'])}, net "
          f"{_f(c['net_return'])}, NIFTY 200 {_f(c['nifty200_return'])}.", "",
          "**F&O-eligible proxy universe** (top 140 by trailing 60-day median traded value):", "",
          "| Period | Gross Sharpe | Net Sharpe |", "|---|---|---|"]
    for p, v in rb["fno_proxy_universe"].items():
        L.append(f"| {p} | {_f(v['gross'], 2)} | {_f(v['net'], 2)} |")
    L += ["", "## Earnings event study (not in the composite; sign fixed a priori = +1)", "",
          "Source: quarterly results CSV. NIFTY 200 coverage starts 2022, so there is no train period. "
          "Values are held for 60 trading days after the first close at/after the filing timestamp.", "",
          "| Signal | Period | IC | t | Median live names | Decile spread bps/day | L/S gross Sharpe |",
          "|---|---|---|---|---|---|---|"]
    for k, s in r.get("event_study", {}).items():
        for p in ["validation", "test"]:
            v = s[p]
            L.append(f"| {k} | {p} | {_f(v['ic_mean'], 4)} | {_f(v['t_stat'], 2)} | {_f(v['median_live_names'], 0)} | "
                     f"{_f(v['decile_spread_bps'], 1)} | {_f(v['ls_gross_sharpe'], 2)} |")
    L += ["", "## Model selection (validation only)", "",
          "| Candidate | Val gross Sharpe | Val net Sharpe |", "|---|---|---|"]
    for k, v in r["candidates_validation"].items():
        L.append(f"| {k} | {_f(v['val_gross_sharpe'], 2)} | {_f(v['val_net_sharpe'], 2)} |")
    L += ["", f"Ridge alpha by validation IC: " + ", ".join(f"{k:g}: {_f(v, 4)}" for k, v in
                                                            r["ridge"]["alpha_validation_ic"].items()),
          "", f"Costs per unit traded: long leg (cash delivery) {r['costs_bps_per_unit_traded']['long_leg_delivery']:.1f} bps, "
              f"short leg (stock futures) {r['costs_bps_per_unit_traded']['short_leg_futures']:.1f} bps, incl. 7.5 bps slippage.",
          "", "## Data quality", "", "```", json.dumps(r["data_quality"], indent=2),
          json.dumps(r["events"], indent=2), "```", ""]
    return "\n".join(L)


if __name__ == "__main__":
    raise SystemExit(main())

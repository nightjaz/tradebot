"""No-lookahead and correctness tests for engine/research on synthetic data with known answers."""
import sys
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from research import backtest as bt  # noqa: E402
from research.data import forward_returns  # noqa: E402
from research.evaluate import daily_ic  # noqa: E402
from research.events import event_panel, seasonal_surprise, signal_date, yoy_profit_surprise  # noqa: E402
from research.model import walk_forward_ridge  # noqa: E402
from research.signals import PRICE_SIGNALS, process  # noqa: E402


def synthetic_panels(n_days=400, n_stocks=60, seed=0):
    rng = np.random.default_rng(seed)
    idx = pd.bdate_range("2016-01-01", periods=n_days)
    cols = [f"S{i}" for i in range(n_stocks)]
    close = pd.DataFrame(100 * np.exp(np.cumsum(rng.normal(0, 0.02, (n_days, n_stocks)), axis=0)), idx, cols)
    open_ = close.shift(1).fillna(close) * np.exp(rng.normal(0, 0.005, close.shape))
    high = np.maximum(open_, close) * 1.01
    low = np.minimum(open_, close) * 0.99
    vol = pd.DataFrame(rng.integers(1_000, 100_000, close.shape).astype(float), idx, cols)
    index_close = close.mean(axis=1)
    return {"open": open_, "high": high, "low": low, "close": close, "volume": vol, "index_close": index_close}


def perturb_after(p, t0, seed=1):
    rng = np.random.default_rng(seed)
    out = {}
    for k, v in p.items():
        v = v.copy()
        noise = rng.uniform(0.5, 2.0, v.loc[v.index > t0].shape)
        v.loc[v.index > t0] = v.loc[v.index > t0] * noise
        out[k] = v
    return out


class TestTiming(unittest.TestCase):
    def test_forward_return_is_next_open_to_following_open(self):
        idx = pd.bdate_range("2020-01-01", periods=6)
        o = pd.DataFrame({"A": [10, 11, 12, 13, 14, 15.0]}, index=idx)
        f = forward_returns(o)
        self.assertAlmostEqual(f.iloc[0, 0], 12 / 11 - 1)  # signal at day0 close -> buy day1 open, sell day2 open
        self.assertTrue(np.isnan(f.iloc[-2, 0]))
        d = forward_returns(o, delay=1)
        self.assertAlmostEqual(d.iloc[0, 0], 13 / 12 - 1)

    def test_every_price_signal_uses_only_past_data(self):
        p = synthetic_panels()
        t0 = p["close"].index[300]
        q = perturb_after(p, t0)
        for name, fn in PRICE_SIGNALS.items():
            a, b = fn(p).loc[:t0], fn(q).loc[:t0]
            pd.testing.assert_frame_equal(a, b, check_exact=False, obj=name)
            self.assertGreater(a.loc[t0].notna().sum(), 0, name)

    def test_future_changes_alter_future_signal(self):
        # sanity: the perturbation actually reaches signals after t0, so the test above is not vacuous
        p = synthetic_panels()
        t0 = p["close"].index[300]
        q = perturb_after(p, t0)
        a = PRICE_SIGNALS["reversal_5d"](p).iloc[-1]
        b = PRICE_SIGNALS["reversal_5d"](q).iloc[-1]
        self.assertFalse(np.allclose(a, b))

    def test_processing_is_row_local(self):
        p = synthetic_panels()
        s = PRICE_SIGNALS["reversal_5d"](p)
        sectors = pd.Series({c: f"sec{i % 5}" for i, c in enumerate(s.columns)})
        z = process(s, sectors)
        t0 = s.index[300]
        s2 = s.copy()
        s2.loc[s2.index > t0] *= 3
        pd.testing.assert_frame_equal(z.loc[:t0], process(s2, sectors).loc[:t0])
        row = z.dropna(how="all").iloc[-1]
        self.assertAlmostEqual(row.mean(), 0, places=8)
        self.assertAlmostEqual(row.std(), 1, places=8)


class TestEvents(unittest.TestCase):
    cal = pd.DatetimeIndex(pd.to_datetime(["2024-01-04", "2024-01-05", "2024-01-08", "2024-01-09", "2024-01-10"]))

    def test_after_close_filing_lands_next_trading_day(self):
        ts = pd.Series(pd.to_datetime(["2024-01-05 17:10", "2024-01-05 14:00", "2024-01-05 15:30",
                                       "2024-01-06 11:00", "2024-01-04 09:00"]))
        got = signal_date(ts, self.cal).dt.strftime("%Y-%m-%d").tolist()
        self.assertEqual(got, ["2024-01-08", "2024-01-05", "2024-01-05", "2024-01-08", "2024-01-04"])

    def test_event_panel_starts_on_signal_date_and_expires(self):
        ev = pd.DataFrame({"symbol": ["A"], "timestamp": pd.to_datetime(["2024-01-05 18:00"]), "v": [1.5]})
        panel = event_panel(ev, "v", self.cal, ["A"], hold_days=2)
        self.assertTrue(panel["A"].iloc[:2].isna().all())     # unknown on 4th and 5th (filed after close on 5th)
        self.assertEqual(panel["A"].iloc[2:4].tolist(), [1.5, 1.5])
        self.assertTrue(np.isnan(panel["A"].iloc[4]))           # expired after hold_days

    def test_surprise_does_not_use_later_quarters(self):
        periods = pd.date_range("2015-03-31", periods=16, freq="QE")
        rng = np.random.default_rng(3)
        ev = pd.DataFrame({"symbol": "A", "period": periods, "net_profit": rng.normal(100, 10, 16),
                           "sales": 1000.0})
        base = seasonal_surprise(ev, "net_profit")
        base_yoy = yoy_profit_surprise(ev)
        ev2 = ev.copy()
        ev2.loc[12:, "net_profit"] = 1e6
        pd.testing.assert_series_equal(base.iloc[:12], seasonal_surprise(ev2, "net_profit").iloc[:12])
        pd.testing.assert_series_equal(base_yoy.iloc[:12], yoy_profit_surprise(ev2).iloc[:12])
        self.assertTrue(base.iloc[:8].isna().all())  # needs 4 prior seasonal changes before it exists


class TestEvaluationAndBacktest(unittest.TestCase):
    def setUp(self):
        rng = np.random.default_rng(5)
        idx = pd.bdate_range("2016-01-01", periods=300)
        self.fwd = pd.DataFrame(rng.normal(0, 0.02, (300, 80)), idx, [f"S{i}" for i in range(80)])
        self.tradeable = self.fwd.notna()

    def test_ic_known_values(self):
        self.assertTrue(np.allclose(daily_ic(self.fwd, self.fwd), 1.0))
        self.assertTrue(np.allclose(daily_ic(-self.fwd, self.fwd), -1.0))
        noise = pd.DataFrame(np.random.default_rng(9).normal(size=self.fwd.shape), self.fwd.index, self.fwd.columns)
        self.assertLess(abs(daily_ic(noise, self.fwd).mean()), 0.02)

    def test_perfect_foresight_wins_and_noise_does_not(self):
        cm = bt.CostModel(multiplier=0)
        good = bt.run(bt.build_weights(self.fwd, self.tradeable), self.fwd, cm)
        self.assertGreater(bt.metrics(good["gross"])["sharpe"], 10)
        noise = pd.DataFrame(np.random.default_rng(11).normal(size=self.fwd.shape), self.fwd.index, self.fwd.columns)
        bad = bt.run(bt.build_weights(noise, self.tradeable), self.fwd, cm)
        self.assertLess(abs(bt.metrics(bad["gross"])["sharpe"]), 2)

    def test_weights_are_dollar_neutral_and_capped(self):
        w = bt.build_weights(self.fwd, self.tradeable, max_weight=1.0)  # 80 names -> 16 per leg
        self.assertTrue(np.allclose(w.sum(axis=1), 0))
        self.assertTrue(np.allclose(w.clip(lower=0).sum(axis=1), 1))  # uncapped: 1/16 each
        capped = bt.build_weights(self.fwd, self.tradeable, max_weight=0.05)
        self.assertLessEqual(capped.abs().max().max(), 0.05 + 1e-9)
        self.assertTrue(np.allclose(capped.sum(axis=1), 0))
        self.assertTrue(np.allclose(capped.clip(lower=0).sum(axis=1), 16 * 0.05))  # under-invested, not over-cap
        wide = bt.build_weights(self.fwd, self.tradeable, frac=0.5, max_weight=0.04)  # 40 per leg: cap not binding
        self.assertTrue(np.allclose(wide.clip(lower=0).sum(axis=1), 1))

    def test_costs_charged_only_on_trades(self):
        w = bt.build_weights(self.fwd.iloc[[0]].reindex(self.fwd.index).ffill(), self.tradeable)
        res = bt.run(w, self.fwd, bt.CostModel())
        self.assertGreater(res["cost"].iloc[0], 0)
        self.assertTrue((res["cost"].iloc[1:] == 0).all())

    def test_walk_forward_does_not_see_test_year_labels(self):
        rng = np.random.default_rng(2)
        idx = pd.bdate_range("2015-01-01", "2018-12-31")
        cols = [f"S{i}" for i in range(50)]
        z = {f"f{k}": pd.DataFrame(rng.normal(size=(len(idx), 50)), idx, cols) for k in range(3)}
        fwd = pd.DataFrame(rng.normal(size=(len(idx), 50)), idx, cols)
        p1, _ = walk_forward_ridge(z, fwd, alpha=1.0, first_test_year=2017, last_year=2018)
        fwd2 = fwd.copy()
        fwd2.loc["2017-12-15":] = rng.normal(size=fwd2.loc["2017-12-15":].shape) * 50  # rewrite late-2017+ labels
        p2, _ = walk_forward_ridge(z, fwd2, alpha=1.0, first_test_year=2017, last_year=2018)
        pd.testing.assert_frame_equal(p1.loc["2017"], p2.loc["2017"])  # 2017 model trained only on <= 2016


if __name__ == "__main__":
    unittest.main()

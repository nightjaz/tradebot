import unittest
from datetime import datetime, timedelta, timezone

from edgesignal.impact import build_reddit_impact_dataset
from edgesignal.models import MarketBar
from edgesignal.sentiment import make_event


class ImpactTests(unittest.TestCase):
    def test_joins_only_reddit_features_to_future_returns_without_lookahead(self):
        start = datetime(2026, 8, 10, 4, 0, tzinfo=timezone.utc)
        reddit = make_event("reddit:r/test", "r1", "SBIN", start + timedelta(minutes=1),
            "SBIN strong growth", "profit beat", .4, metadata={"engagement": .8, "promotional": 0})
        news = make_event("news", "n1", "SBIN", start + timedelta(minutes=2),
            "SBIN strong order", "", .9)
        bars = [MarketBar("SBIN", start + timedelta(minutes=minute), 100, 101, 99, 100 + minute,
            1000, 100, 0, 1, 1) for minute in range(5, 70, 5)]
        rows = build_reddit_impact_dataset([reddit, news], bars)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["mention_count"], 1)
        self.assertEqual(rows[0]["baseline_close"], 105)
        self.assertAlmostEqual(rows[0]["return_5m"], 110 / 105 - 1, places=8)

    def test_drops_window_without_all_requested_future_horizons(self):
        start = datetime(2026, 8, 10, 4, 0, tzinfo=timezone.utc)
        event = make_event("reddit:r/test", "r1", "SBIN", start + timedelta(minutes=1), "SBIN strong", "", .4)
        bars = [MarketBar("SBIN", start + timedelta(minutes=5), 100, 101, 99, 100, 1000, 100, 0, 1, 1)]
        self.assertEqual(build_reddit_impact_dataset([event], bars), [])


if __name__ == "__main__":
    unittest.main()

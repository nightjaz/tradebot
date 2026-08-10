import tempfile
import unittest
from datetime import datetime, timedelta, timezone

from edgesignal.blogs import BlogIngestor, BlogSpec
from edgesignal.ledger import Ledger
from edgesignal.rss import FeedItem, SymbolResolver


class BlogTests(unittest.TestCase):
    def setUp(self):
        self.now = datetime(2026, 8, 10, 5, 0, tzinfo=timezone.utc)
        self.ingestor = BlogIngestor(SymbolResolver({"SBIN": ["SBIN", "SBI"]}))
        self.spec = BlogSpec("Example", "https://example.com/feed", .6, max_age_hours=24)

    def test_maps_recent_stock_specific_post_and_caps_excerpt(self):
        item = FeedItem("1", "SBI profit growth", "SBIN " + "strong " * 100,
            "https://example.com/1", self.now - timedelta(hours=1))
        event = self.ingestor.transform(self.spec, [item], self.now)[0]
        self.assertEqual(event.symbol, "SBIN")
        self.assertTrue(event.source.startswith("blog:"))
        self.assertLessEqual(len(event.body), 280)
        self.assertNotIn("author", event.metadata)

    def test_filters_stale_and_future_posts(self):
        old = FeedItem("1", "SBI old", "", "", self.now - timedelta(days=2))
        future = FeedItem("2", "SBI future", "", "", self.now + timedelta(minutes=10))
        self.assertEqual(self.ingestor.transform(self.spec, [old, future], self.now), [])

    def test_downweights_promotional_language(self):
        clean = FeedItem("1", "SBI quarterly analysis", "profit growth", "", self.now)
        promo = FeedItem("2", "SBI guaranteed multibagger", "buy now", "", self.now)
        events = self.ingestor.transform(self.spec, [clean, promo], self.now)
        self.assertLess(events[1].credibility, events[0].credibility)

    def test_blog_retention_does_not_delete_news(self):
        with tempfile.TemporaryDirectory() as directory:
            ledger = Ledger(f"{directory}/events.db")
            old = self.ingestor.transform(BlogSpec("Example", "https://example.com/feed", .6, max_age_hours=1000),
                [FeedItem("1", "SBI analysis", "", "", self.now - timedelta(days=20))], self.now)[0]
            ledger.event(old)
            self.assertEqual(ledger.prune_events("blog:%", self.now - timedelta(days=14)), 1)
            ledger.close()


if __name__ == "__main__":
    unittest.main()

import tempfile
import unittest
from datetime import datetime, timedelta, timezone

from edgesignal.ledger import Ledger
from edgesignal.reddit import RedditIngestor, RedditOAuthClient, SubredditSpec, parse_listing
from edgesignal.rss import SymbolResolver
from edgesignal.sentiment import make_event


class RedditTests(unittest.TestCase):
    def setUp(self):
        self.now = datetime(2026, 8, 10, 5, 0, tzinfo=timezone.utc)
        self.resolver = SymbolResolver({"SBIN": ["SBIN", "SBI"], "RELIANCE": ["RELIANCE"]})

    def test_oauth_credentials_and_contact_user_agent_are_required(self):
        with self.assertRaises(ValueError):
            RedditOAuthClient("", "", "")
        with self.assertRaises(ValueError):
            RedditOAuthClient("client", "secret", "EdgeSignal/0.3")

    def test_listing_parser_collects_no_username(self):
        payload = {"data": {"children": [{"data": {
            "name": "t3_abc", "subreddit": "IndianStockMarket", "author": "private_user",
            "title": "SBI shows strength", "selftext": "SBIN above VWAP", "permalink": "/r/x/abc",
            "created_utc": self.now.timestamp(), "score": 12, "num_comments": 4, "upvote_ratio": .8,
        }}]}}
        post = parse_listing(payload)[0]
        self.assertEqual(post.source_id, "t3_abc")
        self.assertFalse(hasattr(post, "author"))

    def test_transform_filters_stickies_and_downweights_promotions(self):
        payload = {"data": {"children": [
            {"data": {"name": "t3_good", "subreddit": "IndianStockMarket", "title": "SBI profit growth",
                "selftext": "SBIN volume is strong", "permalink": "/r/x/good", "created_utc": self.now.timestamp(),
                "score": 40, "num_comments": 10, "upvote_ratio": .9}},
            {"data": {"name": "t3_promo", "subreddit": "IndianStockMarket", "title": "SBI guaranteed target price",
                "selftext": "Buy SBIN now", "permalink": "/r/x/promo", "created_utc": self.now.timestamp(),
                "score": 40, "num_comments": 10, "upvote_ratio": .9}},
            {"data": {"name": "t3_sticky", "subreddit": "IndianStockMarket", "title": "SBI daily thread",
                "selftext": "SBIN", "permalink": "/r/x/sticky", "created_utc": self.now.timestamp(), "stickied": True}},
        ]}}
        events = RedditIngestor(self.resolver).transform(SubredditSpec("IndianStockMarket", .5), parse_listing(payload))
        self.assertEqual(len(events), 2)
        self.assertLess(events[1].credibility, events[0].credibility)

    def test_reddit_retention_prunes_old_events_only(self):
        with tempfile.TemporaryDirectory() as directory:
            ledger = Ledger(f"{directory}/events.db")
            old = make_event("reddit:r/test", "1", "SBIN", self.now - timedelta(days=20), "SBI old", "", .3)
            news = make_event("news", "2", "SBIN", self.now - timedelta(days=20), "SBI filing", "", .9)
            ledger.event(old); ledger.event(news)
            self.assertEqual(ledger.prune_events("reddit:%", self.now - timedelta(days=14)), 1)
            self.assertEqual(ledger.summary()["events"], 1)
            ledger.close()


if __name__ == "__main__":
    unittest.main()

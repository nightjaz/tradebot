import tempfile
import unittest
from datetime import datetime, timezone

from edgesignal.ledger import Ledger
from edgesignal.rss import FeedSpec, RssIngestor, SymbolResolver, parse_feed

RSS = b'''<?xml version="1.0"?><rss version="2.0"><channel><item>
<guid>story-1</guid><title>Tata Motors wins record order</title>
<description><![CDATA[Strong growth for Tata Motors and SBI]]></description>
<link>https://example.test/story-1</link><pubDate>Mon, 10 Aug 2026 04:30:00 GMT</pubDate>
</item></channel></rss>'''

ATOM = b'''<?xml version="1.0"?><feed xmlns="http://www.w3.org/2005/Atom"><entry>
<id>a-1</id><title>Infosys issues warning</title><summary>Weak outlook</summary>
<link href="https://example.test/a-1"/><updated>2026-08-10T05:00:00Z</updated>
</entry></feed>'''


class RssTests(unittest.TestCase):
    def test_parses_rss_and_atom(self):
        self.assertEqual(parse_feed(RSS)[0].source_id, "story-1")
        self.assertEqual(parse_feed(ATOM)[0].url, "https://example.test/a-1")

    def test_resolves_symbols_and_preserves_multi_company_story(self):
        resolver=SymbolResolver({"TATAMOTORS":["Tata Motors"],"SBIN":["SBI"]})
        events=RssIngestor(resolver).transform(FeedSpec("fixture","https://example.test",.8),parse_feed(RSS))
        self.assertEqual([event.symbol for event in events],["SBIN","TATAMOTORS"])
        with tempfile.TemporaryDirectory() as d:
            ledger=Ledger(f"{d}/rss.db")
            self.assertEqual(sum(ledger.event(event) for event in events),2)
            self.assertEqual(sum(ledger.event(event) for event in events),0)
            ledger.close()

    def test_unmatched_story_does_not_become_trade_event(self):
        resolver=SymbolResolver({"INFY":["Infosys"]})
        items=parse_feed(RSS,datetime.now(timezone.utc))
        self.assertEqual(RssIngestor(resolver).transform(FeedSpec("fixture","x",.8),items),[])


if __name__ == "__main__": unittest.main()

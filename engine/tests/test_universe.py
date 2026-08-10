import json
import unittest
from pathlib import Path

from edgesignal.rss import SymbolResolver


ROOT = Path(__file__).parents[2]


class UniverseTests(unittest.TestCase):
    def test_nifty_200_snapshot_has_exactly_200_unique_symbols(self):
        payload = json.loads((ROOT / "config/symbol_aliases.json").read_text(encoding="utf-8"))
        self.assertEqual(payload["universe"], "NIFTY 200")
        self.assertEqual(payload["constituent_count"], 200)
        self.assertEqual(len(payload["aliases"]), 200)

    def test_resolves_curated_names_and_special_tickers(self):
        resolver = SymbolResolver.from_json(ROOT / "config/symbol_aliases.json")
        self.assertEqual(resolver.resolve("SBI and Mahindra & Mahindra were active"), ["M&M", "SBIN"])
        self.assertEqual(resolver.resolve("NSE:OIL rose while oil prices fell"), ["OIL"])

    def test_ambiguous_tickers_do_not_match_ordinary_words(self):
        resolver = SymbolResolver.from_json(ROOT / "config/symbol_aliases.json")
        self.assertEqual(resolver.resolve("This page discusses an idea about oil demand"), [])
        self.assertEqual(resolver.resolve("Stocks listed on BSE declined"), [])
        self.assertEqual(resolver.resolve("BSE Ltd. shares advanced"), ["BSE"])


if __name__ == "__main__":
    unittest.main()

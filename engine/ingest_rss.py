import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from edgesignal.ledger import Ledger
from edgesignal.rss import RssIngestor, SymbolResolver, load_feed_specs


def main() -> int:
    parser = argparse.ArgumentParser(description="Ingest configured RSS headlines into the EdgeSignal event ledger")
    parser.add_argument("--feeds", default="config/feeds.json")
    parser.add_argument("--aliases", default="config/symbol_aliases.json")
    parser.add_argument("--db", default="data/edgesignal.db")
    args = parser.parse_args()
    ledger = Ledger(args.db)
    ingestor = RssIngestor(SymbolResolver.from_json(args.aliases))
    report = []
    try:
        for spec in load_feed_specs(args.feeds):
            try:
                events = ingestor.fetch(spec)
                inserted = sum(ledger.event(event) for event in events)
                report.append({"feed": spec.name, "events": len(events), "inserted": inserted, "status": "ok"})
            except Exception as exc:
                report.append({"feed": spec.name, "events": 0, "inserted": 0, "status": "error", "error": str(exc)})
    finally:
        ledger.close()
    print(json.dumps(report, indent=2))
    return 0 if any(row["status"] == "ok" for row in report) else 1


if __name__ == "__main__":
    raise SystemExit(main())

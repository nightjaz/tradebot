import argparse
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from edgesignal.blogs import BlogIngestor, load_blog_specs
from edgesignal.ledger import Ledger
from edgesignal.rss import SymbolResolver


def main() -> int:
    parser = argparse.ArgumentParser(description="Ingest allowlisted analysis blogs into EdgeSignal")
    parser.add_argument("--config", default="config/blogs.json")
    parser.add_argument("--aliases", default="config/symbol_aliases.json")
    parser.add_argument("--db", default="data/edgesignal.db")
    args = parser.parse_args()
    specs, retention_days = load_blog_specs(args.config)
    ingestor = BlogIngestor(SymbolResolver.from_json(args.aliases))
    ledger = Ledger(args.db)
    report = []
    try:
        ledger.prune_events("blog:%", datetime.now(timezone.utc) - timedelta(days=retention_days))
        for spec in specs:
            try:
                items = ingestor.fetch_items(spec)
                events = ingestor.transform(spec, items)
                inserted = sum(ledger.event(event) for event in events)
                report.append({"blog": spec.name, "items": len(items), "events": len(events),
                    "inserted": inserted, "status": "ok"})
            except Exception as exc:
                report.append({"blog": spec.name, "items": 0, "events": 0, "inserted": 0,
                    "status": "error", "error": str(exc)})
    finally:
        ledger.close()
    print(json.dumps(report, indent=2))
    return 0 if any(row["status"] == "ok" for row in report) else 1


if __name__ == "__main__":
    raise SystemExit(main())

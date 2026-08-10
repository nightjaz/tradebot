import argparse
import json
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from edgesignal.ledger import Ledger
from edgesignal.reddit import RedditIngestor, RedditOAuthClient, load_subreddits
from edgesignal.rss import SymbolResolver


def main() -> int:
    parser = argparse.ArgumentParser(description="Ingest allowlisted Reddit posts into the EdgeSignal event ledger")
    parser.add_argument("--config", default="config/reddit.json")
    parser.add_argument("--aliases", default="config/symbol_aliases.json")
    parser.add_argument("--db", default="data/edgesignal.db")
    args = parser.parse_args()
    specs, retention_days = load_subreddits(args.config)
    client_id = os.getenv("REDDIT_CLIENT_ID", "")
    client_secret = os.getenv("REDDIT_CLIENT_SECRET", "")
    user_agent = os.getenv("REDDIT_USER_AGENT", "")
    if not all((client_id, client_secret, user_agent)):
        print(json.dumps({"status": "configuration_required", "message":
            "Set REDDIT_CLIENT_ID, REDDIT_CLIENT_SECRET, and REDDIT_USER_AGENT after Reddit approves Data API access."}, indent=2))
        return 2
    client = RedditOAuthClient(client_id, client_secret, user_agent)
    ingestor = RedditIngestor(SymbolResolver.from_json(args.aliases))
    ledger = Ledger(args.db)
    report = []
    try:
        cutoff = datetime.now(timezone.utc) - timedelta(days=retention_days)
        ledger.prune_events("reddit:%", cutoff)
        for spec in specs:
            try:
                events = ingestor.transform(spec, client.newest(spec))
                inserted = sum(ledger.event(event) for event in events)
                report.append({"subreddit": spec.name, "events": len(events), "inserted": inserted, "status": "ok"})
            except Exception as exc:
                report.append({"subreddit": spec.name, "events": 0, "inserted": 0, "status": "error", "error": str(exc)})
    finally:
        ledger.close()
    print(json.dumps(report, indent=2))
    return 0 if any(row["status"] == "ok" for row in report) else 1


if __name__ == "__main__":
    raise SystemExit(main())

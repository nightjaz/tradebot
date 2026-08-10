import argparse
import csv
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from edgesignal.impact import build_reddit_impact_dataset
from edgesignal.ledger import Ledger
from edgesignal.providers import CsvBarProvider


def main() -> int:
    parser = argparse.ArgumentParser(description="Join Reddit features to later candle returns")
    parser.add_argument("--db", default="data/edgesignal.db")
    parser.add_argument("--bars", required=True, help="CSV containing timestamped market bars")
    parser.add_argument("--output", default="data/reddit_impact.csv")
    args = parser.parse_args()
    ledger = Ledger(args.db)
    try:
        rows = build_reddit_impact_dataset(ledger.load_events("reddit:%"), list(CsvBarProvider(args.bars).bars()))
    finally:
        ledger.close()
    if not rows:
        print("No complete Reddit/candle windows were available; no dataset was written.")
        return 1
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    print(f"Wrote {len(rows)} observations to {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

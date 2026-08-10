import argparse
import csv
import json
import re
from datetime import date
from pathlib import Path


SOURCE_URL = "https://www.niftyindices.com/IndexConstituent/ind_nifty200list.csv"
AMBIGUOUS_TICKERS = {"BSE", "ETERNAL", "IDEA", "MANKIND", "OIL", "PAGE"}


def company_aliases(name: str) -> list[str]:
    aliases = [name.strip()]
    base = re.sub(r"\s+(?:Ltd\.?|Limited)$", "", name.strip(), flags=re.I)
    if base != name.strip():
        aliases.append(base)
    without_india = re.sub(r"\s+\(India\)$", "", base, flags=re.I)
    if without_india != base:
        aliases.append(without_india)
    return aliases


def build_aliases(csv_path: Path, overrides_path: Path) -> dict[str, list[str]]:
    with csv_path.open(newline="", encoding="utf-8-sig") as handle:
        rows = list(csv.DictReader(handle))
    symbols = [row["Symbol"].strip().upper() for row in rows]
    if len(rows) != 200 or len(set(symbols)) != 200:
        raise ValueError(f"Expected 200 unique Nifty 200 constituents, received {len(rows)} rows and {len(set(symbols))} symbols")
    overrides = json.loads(overrides_path.read_text(encoding="utf-8"))
    result = {}
    for row, symbol in zip(rows, symbols):
        candidates = company_aliases(row["Company Name"])
        if symbol in AMBIGUOUS_TICKERS:
            candidates = [value for value in candidates if value.casefold() != symbol.casefold()]
        candidates.extend([f"NSE:{symbol}", f"${symbol}"])
        if symbol not in AMBIGUOUS_TICKERS and len(symbol) >= 3:
            candidates.append(symbol)
        candidates.extend(overrides.get(symbol, []))
        seen = set()
        result[symbol] = [value for value in candidates
            if value and not (value.casefold() in seen or seen.add(value.casefold()))]
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate EdgeSignal aliases from an official Nifty 200 constituent snapshot")
    parser.add_argument("--csv", default="config/nifty200.csv")
    parser.add_argument("--overrides", default="config/symbol_alias_overrides.json")
    parser.add_argument("--output", default="config/symbol_aliases.json")
    args = parser.parse_args()
    aliases = build_aliases(Path(args.csv), Path(args.overrides))
    payload = {"universe": "NIFTY 200", "constituent_count": len(aliases),
        "snapshot_date": date.today().isoformat(), "source": SOURCE_URL, "aliases": aliases}
    Path(args.output).write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Wrote {len(aliases)} symbols to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

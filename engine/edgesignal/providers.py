import csv
from datetime import datetime
from pathlib import Path

from .models import MarketBar


class CsvBarProvider:
    def __init__(self, path: str | Path): self.path=Path(path)
    def bars(self):
        with self.path.open(newline="",encoding="utf-8") as f:
            for r in csv.DictReader(f):
                yield MarketBar(r["symbol"],datetime.fromisoformat(r["timestamp"]),*[float(r[k]) for k in ("open","high","low","close")],int(r["volume"]),float(r["vwap"]),float(r.get("relative_strength",0)),float(r.get("volume_ratio",1)),float(r.get("atr",0)))


class TelegramProvider:
    def __init__(self, *args, **kwargs):
        raise RuntimeError("Telegram ingestion needs an approved public-channel list and Telegram API credentials")

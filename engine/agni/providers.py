import csv
import json
from datetime import datetime
from pathlib import Path
from urllib.request import Request, urlopen

from .models import MarketBar


class CsvBarProvider:
    def __init__(self, path: str | Path): self.path=Path(path)
    def bars(self):
        with self.path.open(newline="",encoding="utf-8") as f:
            for r in csv.DictReader(f):
                yield MarketBar(r["symbol"],datetime.fromisoformat(r["timestamp"]),*[float(r[k]) for k in ("open","high","low","close")],int(r["volume"]),float(r["vwap"]),float(r.get("relative_strength",0)),float(r.get("volume_ratio",1)),float(r.get("atr",0)))


class RedditPublicProvider:
    """Read-only adapter for public subreddit JSON; use only where permitted."""
    def __init__(self, subreddit: str, user_agent: str="AGNI research bot/0.1"):
        self.url=f"https://www.reddit.com/r/{subreddit}/new.json?limit=100"; self.user_agent=user_agent
    def posts(self):
        req=Request(self.url,headers={"User-Agent":self.user_agent})
        with urlopen(req,timeout=10) as response:
            data=json.load(response)
        return [item["data"] for item in data["data"]["children"]]


class TelegramProvider:
    def __init__(self, *args, **kwargs):
        raise RuntimeError("Telegram ingestion needs an approved public-channel list and Telegram API credentials")

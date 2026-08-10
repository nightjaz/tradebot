from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from .models import IntelligenceEvent
from .rss import FeedItem, SymbolResolver, parse_feed
from .sentiment import make_event


PROMOTIONAL = re.compile(
    r"\b(guaranteed|sure[- ]?shot|buy now|multibagger|jackpot|upper circuit|to the moon|target price|best stock to buy)\b",
    re.I,
)


@dataclass(frozen=True)
class BlogSpec:
    name: str
    url: str
    credibility: float
    enabled: bool = True
    max_age_hours: int = 168
    category: str = "analysis"


def load_blog_specs(path: str | Path) -> tuple[list[BlogSpec], int]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    specs = [BlogSpec(**row) for row in payload["blogs"] if row.get("enabled", True)]
    return specs, int(payload.get("retention_days", 30))


class BlogIngestor:
    def __init__(self, resolver: SymbolResolver, timeout_seconds: int = 15):
        self.resolver = resolver
        self.timeout_seconds = timeout_seconds

    def fetch(self, spec: BlogSpec) -> list[IntelligenceEvent]:
        return self.transform(spec, self.fetch_items(spec))

    def fetch_items(self, spec: BlogSpec) -> list[FeedItem]:
        request = Request(spec.url, headers={"User-Agent": "EdgeSignal/0.4 personal research feed reader"})
        with urlopen(request, timeout=self.timeout_seconds) as response:
            return parse_feed(response.read())

    def transform(self, spec: BlogSpec, items: list[FeedItem], now: datetime | None = None) -> list[IntelligenceEvent]:
        now = now or datetime.now(timezone.utc)
        cutoff = now - timedelta(hours=spec.max_age_hours)
        events: list[IntelligenceEvent] = []
        domain = urlparse(spec.url).netloc.lower()
        for item in items:
            if item.published_at < cutoff or item.published_at > now + timedelta(minutes=5):
                continue
            text = f"{item.title} {item.summary}"
            symbols = self.resolver.resolve(text)
            if not symbols:
                continue
            promotional = bool(PROMOTIONAL.search(text))
            credibility = min(spec.credibility, 0.65) * (0.35 if promotional else 1.0)
            metadata = {"publisher_domain": domain, "category": spec.category,
                "promotional": int(promotional)}
            for symbol in symbols:
                events.append(make_event(f"blog:{spec.name}", item.source_id, symbol, item.published_at,
                    item.title, item.summary[:280], credibility, now, item.url, metadata))
        return events

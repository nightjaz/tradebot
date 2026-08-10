import hashlib
import re
from datetime import datetime

from .models import IntelligenceEvent

POSITIVE = {"beat", "growth", "upgrade", "order", "profit", "surge", "strong", "win", "bullish", "record"}
NEGATIVE = {"cut", "downgrade", "fraud", "loss", "miss", "probe", "weak", "fall", "bearish", "warning"}


def content_hash(text: str) -> str:
    normalized = " ".join(text.lower().split())
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def lexical_sentiment(text: str) -> float:
    words = re.findall(r"[a-z]+", text.lower())
    if not words:
        return 0.0
    raw = sum(word in POSITIVE for word in words) - sum(word in NEGATIVE for word in words)
    return max(-1.0, min(1.0, raw / 4.0))


def make_event(source: str, source_id: str, symbol: str, published_at: datetime,
               title: str, body: str, credibility: float, ingested_at: datetime | None = None,
               url: str = "", metadata: dict[str, float | int | str] | None = None) -> IntelligenceEvent:
    text = f"{title} {body}"
    return IntelligenceEvent(source, source_id, symbol.upper(), published_at,
        ingested_at or datetime.now(published_at.tzinfo), title, body,
        lexical_sentiment(text), max(0.0, min(1.0, credibility)), content_hash(text), url, metadata or {})

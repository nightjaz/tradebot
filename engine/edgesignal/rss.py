from __future__ import annotations

import html
import json
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from urllib.request import Request, urlopen

from .models import IntelligenceEvent
from .sentiment import make_event


@dataclass(frozen=True)
class FeedSpec:
    name: str
    url: str
    credibility: float
    enabled: bool = True
    category: str = "markets"


@dataclass(frozen=True)
class FeedItem:
    source_id: str
    title: str
    summary: str
    url: str
    published_at: datetime


def load_feed_specs(path: str | Path) -> list[FeedSpec]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    return [FeedSpec(**row) for row in payload["feeds"] if row.get("enabled", True)]


def strip_markup(value: str) -> str:
    value = re.sub(r"<[^>]+>", " ", value or "")
    return " ".join(html.unescape(value).split())


def parse_timestamp(value: str, fallback: datetime) -> datetime:
    if not value:
        return fallback
    try:
        result = parsedate_to_datetime(value)
    except (TypeError, ValueError):
        try:
            result = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return fallback
    if result.tzinfo is None:
        result = result.replace(tzinfo=timezone.utc)
    return result


def parse_feed(xml_bytes: bytes, fetched_at: datetime | None = None) -> list[FeedItem]:
    fetched_at = fetched_at or datetime.now(timezone.utc)
    root = ET.fromstring(xml_bytes)
    rows: list[FeedItem] = []
    if root.tag.lower().endswith("feed"):
        entries = [node for node in root if node.tag.lower().endswith("entry")]
    else:
        entries = list(root.findall(".//item"))
    for node in entries:
        fields: dict[str, str] = {}
        link = ""
        for child in node:
            key = child.tag.rsplit("}", 1)[-1].lower()
            text = "".join(child.itertext()).strip()
            fields[key] = text
            if key == "link":
                link = child.attrib.get("href", "") or text
        title = strip_markup(fields.get("title", ""))
        summary = strip_markup(fields.get("description") or fields.get("summary") or fields.get("content", ""))
        url = link or fields.get("guid", "")
        source_id = fields.get("guid") or fields.get("id") or url or title
        published = fields.get("pubdate") or fields.get("published") or fields.get("updated", "")
        if title and source_id:
            rows.append(FeedItem(source_id, title, summary, url, parse_timestamp(published, fetched_at)))
    return rows


class SymbolResolver:
    def __init__(self, aliases: dict[str, list[str]]):
        self.patterns = [(symbol.upper(), re.compile(r"(?<![A-Za-z0-9])" + re.escape(alias) + r"(?![A-Za-z0-9])", re.I))
                         for symbol, names in aliases.items() for alias in names]

    @classmethod
    def from_json(cls, path: str | Path) -> "SymbolResolver":
        return cls(json.loads(Path(path).read_text(encoding="utf-8"))["aliases"])

    def resolve(self, text: str) -> list[str]:
        return sorted({symbol for symbol, pattern in self.patterns if pattern.search(text)})


class RssIngestor:
    def __init__(self, resolver: SymbolResolver, timeout_seconds: int = 15):
        self.resolver = resolver
        self.timeout_seconds = timeout_seconds

    def fetch(self, spec: FeedSpec) -> list[IntelligenceEvent]:
        request = Request(spec.url, headers={"User-Agent": "EdgeSignal/0.2 personal research RSS reader"})
        with urlopen(request, timeout=self.timeout_seconds) as response:
            xml_bytes = response.read()
        return self.transform(spec, parse_feed(xml_bytes))

    def transform(self, spec: FeedSpec, items: list[FeedItem]) -> list[IntelligenceEvent]:
        ingested_at = datetime.now(timezone.utc)
        events: list[IntelligenceEvent] = []
        for item in items:
            text = f"{item.title} {item.summary}"
            for symbol in self.resolver.resolve(text):
                events.append(make_event(spec.name, item.source_id, symbol, item.published_at,
                    item.title, item.summary, spec.credibility, ingested_at, item.url))
        return events

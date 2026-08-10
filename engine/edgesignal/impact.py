from __future__ import annotations

from bisect import bisect_left
from collections import defaultdict
from datetime import datetime, timedelta

from .models import IntelligenceEvent, MarketBar


def _window_end(timestamp: datetime, minutes: int) -> datetime:
    start = timestamp.replace(second=0, microsecond=0, minute=(timestamp.minute // minutes) * minutes)
    return start + timedelta(minutes=minutes)


def build_reddit_impact_dataset(events: list[IntelligenceEvent], bars: list[MarketBar],
                                horizons: tuple[int, ...] = (5, 15, 30, 60),
                                window_minutes: int = 5) -> list[dict]:
    """Join Reddit features available at each window close to later market returns."""
    grouped: dict[tuple[str, datetime], list[IntelligenceEvent]] = defaultdict(list)
    for event in events:
        if event.source.startswith("reddit:"):
            grouped[(event.symbol, _window_end(event.published_at, window_minutes))].append(event)

    bar_groups: dict[str, list[MarketBar]] = defaultdict(list)
    for bar in bars:
        bar_groups[bar.symbol.upper()].append(bar)
    for symbol in bar_groups:
        bar_groups[symbol].sort(key=lambda item: item.timestamp)

    previous_mentions: dict[str, int] = defaultdict(int)
    output = []
    for (symbol, cutoff), window_events in sorted(grouped.items(), key=lambda item: item[0][1]):
        symbol_bars = bar_groups.get(symbol, [])
        timestamps = [bar.timestamp for bar in symbol_bars]
        baseline_index = bisect_left(timestamps, cutoff)
        if baseline_index >= len(symbol_bars):
            continue
        baseline = symbol_bars[baseline_index]
        weights = [event.credibility for event in window_events]
        total_weight = sum(weights) or 1.0
        mentions = len(window_events)
        row = {
            "symbol": symbol,
            "feature_timestamp": cutoff.isoformat(),
            "mention_count": mentions,
            "mention_velocity": round(mentions / max(previous_mentions[symbol], 1), 4),
            "weighted_sentiment": round(sum(event.sentiment * event.credibility for event in window_events) / total_weight, 6),
            "mean_credibility": round(total_weight / mentions, 6),
            "mean_engagement": round(sum(float(event.metadata.get("engagement", 0)) for event in window_events) / mentions, 6),
            "promotional_rate": round(sum(int(event.metadata.get("promotional", 0)) for event in window_events) / mentions, 6),
            "baseline_close": baseline.close,
        }
        complete = True
        for horizon in horizons:
            target_index = bisect_left(timestamps, cutoff + timedelta(minutes=horizon))
            if target_index >= len(symbol_bars):
                complete = False
                break
            row[f"return_{horizon}m"] = round(symbol_bars[target_index].close / baseline.close - 1.0, 8)
        if complete:
            output.append(row)
            previous_mentions[symbol] = mentions
    return output

from collections import defaultdict
from datetime import datetime, timedelta

from .models import IntelligenceEvent, MarketBar, Side, Signal


class SentimentMomentumStrategy:
    """Attention acceleration gated by VWAP, volume, and relative strength."""

    def __init__(self, minimum_score: float = 72.0):
        self.minimum_score = minimum_score

    def score(self, bar: MarketBar, events: list[IntelligenceEvent]) -> Signal | None:
        recent = [e for e in events if e.symbol == bar.symbol and bar.timestamp - timedelta(minutes=60) <= e.published_at <= bar.timestamp]
        if not recent:
            return None
        unique = {e.content_hash: e for e in recent}.values()
        weighted = sum(e.sentiment * e.credibility for e in unique)
        weight = sum(e.credibility for e in unique) or 1.0
        sentiment = weighted / weight
        attention = min(100.0, len(list(unique)) * 18.0)
        direction = 1 if sentiment >= 0 else -1
        price_confirms = (bar.close > bar.vwap and bar.relative_strength > 0) if direction > 0 else (bar.close < bar.vwap and bar.relative_strength < 0)
        price_volume = min(100.0, 45.0 + min(bar.volume_ratio, 3.0) * 18.0 + (15.0 if price_confirms else -25.0))
        sentiment_score = min(100.0, abs(sentiment) * 100.0)
        source_quality = 100.0 * sum(e.credibility for e in unique) / len(list(unique))
        regime = min(100.0, 55.0 + abs(bar.relative_strength) * 300.0)
        score = .35 * price_volume + .25 * sentiment_score + .20 * attention + .10 * source_quality + .10 * regime
        if score < self.minimum_score or not price_confirms or bar.atr <= 0:
            return None
        side = Side.LONG if direction > 0 else Side.SHORT
        stop = bar.close - 1.25 * bar.atr if side is Side.LONG else bar.close + 1.25 * bar.atr
        target = bar.close + 2.5 * bar.atr if side is Side.LONG else bar.close - 2.5 * bar.atr
        return Signal(bar.symbol, bar.timestamp, side, round(score, 2), bar.close, stop, target,
            {"price_volume": price_volume, "sentiment": sentiment_score, "attention": attention,
             "source_quality": source_quality, "market_regime": regime},
            f"{len(list(unique))} independent events; {bar.volume_ratio:.1f}x volume; VWAP and relative strength confirm.")

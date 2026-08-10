from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum


class Side(str, Enum):
    LONG = "LONG"
    SHORT = "SHORT"


@dataclass(frozen=True)
class MarketBar:
    symbol: str
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: int
    vwap: float
    relative_strength: float = 0.0
    volume_ratio: float = 1.0
    atr: float = 0.0


@dataclass(frozen=True)
class IntelligenceEvent:
    source: str
    source_id: str
    symbol: str
    published_at: datetime
    ingested_at: datetime
    title: str
    body: str
    sentiment: float
    credibility: float
    content_hash: str
    url: str = ""
    metadata: dict[str, float | int | str] = field(default_factory=dict)


@dataclass(frozen=True)
class Signal:
    symbol: str
    timestamp: datetime
    side: Side
    score: float
    entry: float
    stop: float
    target: float
    components: dict[str, float]
    thesis: str


@dataclass
class Position:
    symbol: str
    side: Side
    quantity: int
    entry_price: float
    stop: float
    target: float
    opened_at: datetime
    entry_costs: float = 0.0


@dataclass(frozen=True)
class Fill:
    symbol: str
    side: Side
    quantity: int
    price: float
    timestamp: datetime
    costs: float
    reason: str
    realised_pnl: float = 0.0


@dataclass
class Portfolio:
    starting_capital: float
    cash: float
    realised_pnl: float = 0.0
    daily_pnl: float = 0.0
    positions: dict[str, Position] = field(default_factory=dict)
    trades_today: int = 0

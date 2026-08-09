from dataclasses import dataclass
from datetime import time


@dataclass(frozen=True)
class EngineConfig:
    starting_capital: float = 20_000.0
    universe: str = "NIFTY_200"
    risk_per_trade_pct: float = 0.02
    daily_stop_pct: float = 0.06
    max_positions: int = 3
    max_trades_per_day: int = 12
    min_signal_score: float = 72.0
    max_position_pct: float = 0.50
    slippage_bps: float = 5.0
    square_off_at: time = time(15, 15)
    no_new_entries_after: time = time(15, 0)

    def validate(self) -> None:
        if self.starting_capital <= 0:
            raise ValueError("starting_capital must be positive")
        if not 0 < self.risk_per_trade_pct <= 0.05:
            raise ValueError("risk_per_trade_pct must be in (0, 0.05]")
        if not 0 < self.daily_stop_pct <= 0.10:
            raise ValueError("daily_stop_pct must be in (0, 0.10]")
        if self.max_positions < 1 or self.max_trades_per_day < 1:
            raise ValueError("position and trade limits must be positive")

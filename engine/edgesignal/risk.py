from dataclasses import dataclass

from .config import EngineConfig
from .models import Portfolio, Signal


@dataclass(frozen=True)
class RiskDecision:
    approved: bool
    quantity: int = 0
    reason: str = ""


class RiskManager:
    def __init__(self, config: EngineConfig):
        self.config = config

    def evaluate(self, signal: Signal, portfolio: Portfolio) -> RiskDecision:
        if signal.symbol in portfolio.positions:
            return RiskDecision(False, reason="position already open")
        if len(portfolio.positions) >= self.config.max_positions:
            return RiskDecision(False, reason="maximum positions reached")
        if portfolio.trades_today >= self.config.max_trades_per_day:
            return RiskDecision(False, reason="daily trade cap reached")
        if portfolio.daily_pnl <= -self.config.starting_capital * self.config.daily_stop_pct:
            return RiskDecision(False, reason="daily loss limit reached")
        per_share_risk = abs(signal.entry - signal.stop)
        if per_share_risk <= 0:
            return RiskDecision(False, reason="invalid stop distance")
        risk_budget = self.config.starting_capital * self.config.risk_per_trade_pct
        risk_quantity = int(risk_budget / per_share_risk)
        value_quantity = int(self.config.starting_capital * self.config.max_position_pct / signal.entry)
        quantity = min(risk_quantity, value_quantity)
        return RiskDecision(quantity > 0, quantity, "approved" if quantity > 0 else "capital too small")

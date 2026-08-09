from datetime import datetime

from .config import EngineConfig
from .costs import IndianEquityIntradayCosts
from .models import Fill, MarketBar, Portfolio, Position, Side, Signal


class PaperBroker:
    def __init__(self, config: EngineConfig, costs: IndianEquityIntradayCosts | None = None):
        self.config = config
        self.costs = costs or IndianEquityIntradayCosts()

    def enter(self, signal: Signal, quantity: int, next_bar: MarketBar, portfolio: Portfolio) -> Fill:
        slip = self.config.slippage_bps / 10_000
        raw = max(next_bar.open, signal.entry) if signal.side is Side.LONG else min(next_bar.open, signal.entry)
        price = raw * (1 + slip if signal.side is Side.LONG else 1 - slip)
        fee = self.costs.calculate(price * quantity, is_buy=signal.side is Side.LONG)
        portfolio.positions[signal.symbol] = Position(signal.symbol, signal.side, quantity, price, signal.stop, signal.target, next_bar.timestamp, fee)
        portfolio.cash -= fee
        portfolio.trades_today += 1
        return Fill(signal.symbol, signal.side, quantity, round(price, 2), next_bar.timestamp, fee, "signal_entry")

    def mark(self, bar: MarketBar, portfolio: Portfolio, force: bool = False) -> Fill | None:
        position = portfolio.positions.get(bar.symbol)
        if not position:
            return None
        if position.side is Side.LONG:
            exit_price = position.stop if bar.low <= position.stop else position.target if bar.high >= position.target else bar.close
            should_exit = force or bar.low <= position.stop or bar.high >= position.target
            is_buy = False
        else:
            exit_price = position.stop if bar.high >= position.stop else position.target if bar.low <= position.target else bar.close
            should_exit = force or bar.high >= position.stop or bar.low <= position.target
            is_buy = True
        if not should_exit:
            return None
        slip = self.config.slippage_bps / 10_000
        exit_price *= 1 - slip if position.side is Side.LONG else 1 + slip
        gross = ((exit_price - position.entry_price) if position.side is Side.LONG else (position.entry_price - exit_price)) * position.quantity
        exit_fee = self.costs.calculate(exit_price * position.quantity, is_buy=is_buy)
        net = gross - position.entry_costs - exit_fee
        portfolio.realised_pnl += net
        portfolio.daily_pnl += net
        portfolio.cash += net
        del portfolio.positions[bar.symbol]
        reason = "square_off" if force else "stop_or_target"
        return Fill(bar.symbol, position.side, position.quantity, round(exit_price, 2), bar.timestamp, exit_fee, reason, round(net, 2))

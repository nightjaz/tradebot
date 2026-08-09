from .alerts import AlertSink, fill_message, signal_message
from .config import EngineConfig
from .execution import PaperBroker
from .ledger import Ledger
from .models import IntelligenceEvent, MarketBar, Portfolio, Signal
from .risk import RiskManager
from .strategy import SentimentMomentumStrategy


class TradingEngine:
    def __init__(self, config: EngineConfig, ledger: Ledger, alerts: list[AlertSink] | None = None):
        config.validate()
        self.config=config; self.ledger=ledger; self.alerts=alerts or []
        self.strategy=SentimentMomentumStrategy(config.min_signal_score)
        self.risk=RiskManager(config); self.broker=PaperBroker(config)
        self.portfolio=Portfolio(config.starting_capital, config.starting_capital)

    def evaluate(self, bar: MarketBar, events: list[IntelligenceEvent]) -> Signal | None:
        signal=self.strategy.score(bar,events)
        if signal:
            self.ledger.signal(signal)
            for sink in self.alerts: sink.send(signal_message(signal))
        return signal

    def execute(self, signal: Signal, next_bar: MarketBar):
        decision=self.risk.evaluate(signal,self.portfolio)
        if not decision.approved: return None
        fill=self.broker.enter(signal,decision.quantity,next_bar,self.portfolio)
        self.ledger.fill(fill)
        for sink in self.alerts: sink.send(fill_message(fill))
        return fill

    def update(self, bar: MarketBar):
        force=bar.timestamp.time() >= self.config.square_off_at
        fill=self.broker.mark(bar,self.portfolio,force)
        if fill:
            self.ledger.fill(fill)
            for sink in self.alerts: sink.send(fill_message(fill))
        return fill

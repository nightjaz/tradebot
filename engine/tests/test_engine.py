import tempfile
import unittest
from datetime import datetime, timedelta

from edgesignal.config import EngineConfig
from edgesignal.costs import IndianEquityIntradayCosts
from edgesignal.ledger import Ledger
from edgesignal.models import MarketBar, Portfolio
from edgesignal.orchestrator import TradingEngine
from edgesignal.risk import RiskManager
from edgesignal.sentiment import content_hash, make_event


class EngineTests(unittest.TestCase):
    def setUp(self): self.now=datetime.fromisoformat("2026-08-10T10:30:00+05:30")

    def test_content_hash_deduplicates_whitespace_and_case(self):
        self.assertEqual(content_hash("Strong  ORDER Win"),content_hash("strong order win"))

    def test_costs_apply_buy_and_sell_specific_taxes(self):
        model=IndianEquityIntradayCosts()
        self.assertGreater(model.calculate(20_000,False),model.calculate(20_000,True))

    def test_strategy_rejects_future_news(self):
        with tempfile.TemporaryDirectory() as d:
            ledger=Ledger(f"{d}/a.db")
            engine=TradingEngine(EngineConfig(min_signal_score=1),ledger)
            future=make_event("news","1","SBIN",self.now+timedelta(minutes=1),"Strong profit beat","growth surge",.9)
            bar=MarketBar("SBIN",self.now,800,810,798,808,1000,802,.01,2,4)
            self.assertIsNone(engine.evaluate(bar,[future]))
            ledger.close()

    def test_risk_caps_position_value(self):
        config=EngineConfig(); manager=RiskManager(config)
        event=make_event("news","1","SBIN",self.now,"Strong profit beat","growth surge",.9)
        with tempfile.TemporaryDirectory() as d:
            ledger=Ledger(f"{d}/a.db")
            engine=TradingEngine(EngineConfig(min_signal_score=1),ledger)
            signal=engine.evaluate(MarketBar("SBIN",self.now,800,810,798,808,1000,802,.01,2,4),[event])
            self.assertIsNotNone(signal)
            decision=manager.evaluate(signal,Portfolio(20_000,20_000))
            self.assertLessEqual(decision.quantity*signal.entry,10_000)
            ledger.close()


if __name__ == "__main__": unittest.main()

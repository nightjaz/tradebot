from datetime import datetime, timedelta
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent))

from agni import EngineConfig, TradingEngine
from agni.alerts import ConsoleAlert
from agni.ledger import Ledger
from agni.models import MarketBar
from agni.sentiment import make_event


def main() -> None:
    now=datetime.fromisoformat("2026-08-10T10:30:00+05:30")
    config=EngineConfig(min_signal_score=60)
    ledger=Ledger("data/demo.db")
    engine=TradingEngine(config,ledger,[ConsoleAlert()])
    events=[make_event("news","n1","TATAMOTORS",now-timedelta(minutes=20),"Strong order win","Record growth and profit expected",.9),make_event("reddit","r1","TATAMOTORS",now-timedelta(minutes=10),"Bullish volume surge","Strong breakout",.55),make_event("blog","b1","TATAMOTORS",now-timedelta(minutes=5),"Upgrade after order beat","Growth outlook strong",.7)]
    for event in events: ledger.event(event)
    signal=engine.evaluate(MarketBar("TATAMOTORS",now,970,983,968,980,250000,974,0.012,2.4,8),events)
    if signal:
        engine.execute(signal,MarketBar("TATAMOTORS",now+timedelta(minutes=5),981,989,978,986,150000,980,0.014,2.1,8))
        engine.update(MarketBar("TATAMOTORS",now+timedelta(minutes=35),986,1002,985,999,180000,990,0.018,2.0,8))
    print(ledger.summary())
    ledger.close()


if __name__ == "__main__": main()

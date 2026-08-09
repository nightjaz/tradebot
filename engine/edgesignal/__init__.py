"""EdgeSignal intraday research and paper-trading engine."""

from .config import EngineConfig
from .orchestrator import TradingEngine

__all__ = ["EngineConfig", "TradingEngine"]

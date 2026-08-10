import json
import sqlite3
from datetime import datetime
from pathlib import Path

from .models import Fill, IntelligenceEvent, Signal

SCHEMA = """
CREATE TABLE IF NOT EXISTS events(id INTEGER PRIMARY KEY, content_hash TEXT NOT NULL, source TEXT NOT NULL, symbol TEXT NOT NULL, published_at TEXT NOT NULL, payload TEXT NOT NULL, UNIQUE(content_hash, symbol));
CREATE TABLE IF NOT EXISTS signals(id INTEGER PRIMARY KEY, symbol TEXT NOT NULL, timestamp TEXT NOT NULL, side TEXT NOT NULL, score REAL NOT NULL, payload TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS fills(id INTEGER PRIMARY KEY, symbol TEXT NOT NULL, timestamp TEXT NOT NULL, reason TEXT NOT NULL, realised_pnl REAL NOT NULL, payload TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS experiments(id INTEGER PRIMARY KEY, name TEXT UNIQUE NOT NULL, status TEXT NOT NULL, config_json TEXT NOT NULL, net_pnl REAL NOT NULL DEFAULT 0, max_drawdown REAL NOT NULL DEFAULT 0);
CREATE INDEX IF NOT EXISTS idx_events_symbol_time ON events(symbol, published_at);
CREATE INDEX IF NOT EXISTS idx_signals_symbol_time ON signals(symbol, timestamp);
CREATE INDEX IF NOT EXISTS idx_fills_time ON fills(timestamp);
"""


class Ledger:
    def __init__(self, path: str | Path = "data/edgesignal.db"):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(self.path)
        self.db.executescript(SCHEMA)
        self.db.execute("PRAGMA optimize")

    def event(self, e: IntelligenceEvent) -> int:
        cursor = self.db.execute("INSERT OR IGNORE INTO events(content_hash,source,symbol,published_at,payload) VALUES(?,?,?,?,?)",
            (e.content_hash,e.source,e.symbol,e.published_at.isoformat(),json.dumps(e.__dict__,default=str)))
        self.db.commit()
        return cursor.rowcount

    def prune_events(self, source_like: str, before: datetime) -> int:
        cursor = self.db.execute("DELETE FROM events WHERE source LIKE ? AND published_at < ?",
            (source_like, before.isoformat()))
        self.db.commit()
        return cursor.rowcount

    def load_events(self, source_like: str | None = None) -> list[IntelligenceEvent]:
        if source_like is None:
            rows = self.db.execute("SELECT payload FROM events ORDER BY published_at").fetchall()
        else:
            rows = self.db.execute("SELECT payload FROM events WHERE source LIKE ? ORDER BY published_at",
                (source_like,)).fetchall()
        events = []
        for (raw,) in rows:
            payload = json.loads(raw)
            payload["published_at"] = datetime.fromisoformat(payload["published_at"])
            payload["ingested_at"] = datetime.fromisoformat(payload["ingested_at"])
            events.append(IntelligenceEvent(**payload))
        return events

    def signal(self, s: Signal) -> None:
        self.db.execute("INSERT INTO signals(symbol,timestamp,side,score,payload) VALUES(?,?,?,?,?)",
            (s.symbol,s.timestamp.isoformat(),s.side.value,s.score,json.dumps(s.__dict__,default=str)))
        self.db.commit()

    def fill(self, f: Fill) -> None:
        self.db.execute("INSERT INTO fills(symbol,timestamp,reason,realised_pnl,payload) VALUES(?,?,?,?,?)",
            (f.symbol,f.timestamp.isoformat(),f.reason,f.realised_pnl,json.dumps(f.__dict__,default=str)))
        self.db.commit()

    def experiment(self, name: str, status: str, config: dict, net_pnl: float = 0, max_drawdown: float = 0) -> None:
        self.db.execute("INSERT INTO experiments(name,status,config_json,net_pnl,max_drawdown) VALUES(?,?,?,?,?) ON CONFLICT(name) DO UPDATE SET status=excluded.status,config_json=excluded.config_json,net_pnl=excluded.net_pnl,max_drawdown=excluded.max_drawdown",
            (name,status,json.dumps(config,default=str),net_pnl,max_drawdown))
        self.db.commit()

    def summary(self) -> dict:
        counts={t:self.db.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0] for t in ("events","signals","fills")}
        counts["realised_pnl"]=self.db.execute("SELECT COALESCE(SUM(realised_pnl),0) FROM fills").fetchone()[0]
        return counts

    def close(self) -> None:
        self.db.close()

import json
from dataclasses import asdict
from typing import Protocol
from urllib.request import Request, urlopen

from .models import Fill, Signal


class AlertSink(Protocol):
    def send(self, message: str) -> None: ...


class ConsoleAlert:
    def send(self, message: str) -> None:
        print(message)


class WebhookAlert:
    def __init__(self, url: str):
        self.url = url

    def send(self, message: str) -> None:
        request = Request(self.url, data=json.dumps({"text": message}).encode(), headers={"Content-Type": "application/json"})
        with urlopen(request, timeout=5):
            pass


def signal_message(signal: Signal) -> str:
    return f"AGNI {signal.side.value} {signal.symbol} | score {signal.score:.1f} | entry {signal.entry:.2f} | stop {signal.stop:.2f} | target {signal.target:.2f}"


def fill_message(fill: Fill) -> str:
    return f"AGNI FILL {fill.symbol} | {fill.quantity} @ {fill.price:.2f} | {fill.reason} | P&L {fill.realised_pnl:.2f}"

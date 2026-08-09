from dataclasses import dataclass


@dataclass(frozen=True)
class IndianEquityIntradayCosts:
    brokerage_rate: float = 0.0003
    brokerage_cap: float = 20.0
    stt_sell_rate: float = 0.00025
    exchange_rate: float = 0.0000307
    sebi_rate: float = 0.000001
    stamp_buy_rate: float = 0.00003
    gst_rate: float = 0.18

    def calculate(self, turnover: float, is_buy: bool) -> float:
        brokerage = min(self.brokerage_cap, turnover * self.brokerage_rate)
        exchange = turnover * self.exchange_rate
        sebi = turnover * self.sebi_rate
        gst = (brokerage + exchange + sebi) * self.gst_rate
        stt = 0.0 if is_buy else turnover * self.stt_sell_rate
        stamp = turnover * self.stamp_buy_rate if is_buy else 0.0
        return round(brokerage + exchange + sebi + gst + stt + stamp, 2)

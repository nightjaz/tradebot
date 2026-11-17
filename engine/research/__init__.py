"""Cross-sectional daily research pipeline for NIFTY 200 (signals -> IC -> long-short backtest).

Timing convention used everywhere:
  * signal[t]  uses only data available at day t's close
  * fwd_ret[t] = open[t+2] / open[t+1] - 1  (enter at t+1 open, exit at t+2 open)
"""

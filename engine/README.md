# EdgeSignal engine

Research/paper-trading engine for intraday NSE strategies. It uses only information available at the bar timestamp, fills entries on the next bar, models fees and adverse slippage, and stores every event, signal and fill in SQLite.

Run the deterministic demo from the repository root:

```powershell
$env:PYTHONPATH='engine'; python engine/run_demo.py
python -m unittest discover -s engine/tests
```

External data and execution are adapters. Do not connect a live broker until the paper-trading acceptance gate is passed and the broker's current API/algo requirements have been confirmed.

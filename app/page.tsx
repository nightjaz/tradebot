"use client";

import { useEffect, useState } from "react";

const stocks = [
  { s: "TATAMOTORS", side: "LONG", score: 87, move: "+1.84%", why: "Attention accelerated before a confirmed VWAP breakout. Volume is 2.4× baseline." },
  { s: "SBIN", side: "LONG", score: 81, move: "+1.12%", why: "Mention velocity is 3.8× baseline with positive relative strength." },
  { s: "INFY", side: "SHORT", score: 76, move: "−0.94%", why: "Negative news cluster confirmed by price below VWAP and rising sell volume." },
  { s: "RELIANCE", side: "WATCH", score: 64, move: "+0.31%", why: "Attention is rising, but price confirmation is not strong enough yet." },
];

const feeds = [
  ["SEBI", "REGULATORY", "CONNECTED"],
  ["LIVEMINT", "MARKETS + COMPANIES", "CONNECTED"],
  ["INDIAN EXPRESS", "MARKETS", "CONNECTED"],
  ["ECONOMIC TIMES", "MARKETS", "CONNECTED"],
  ["NSE", "ANNOUNCEMENTS", "PENDING VERIFY"],
  ["REDDIT", "3 ALLOWLISTED COMMUNITIES", "OAUTH REQUIRED"],
  ["BLOGS", "4 CURATED RSS FEEDS", "CONNECTED"],
];

export default function Home() {
  const [armed, setArmed] = useState(false);
  const [universe, setUniverse] = useState("NIFTY 200");
  const [pick, setPick] = useState(0);
  const [sync, setSync] = useState("SIMULATED");

  useEffect(() => {
    fetch("/api/dashboard")
      .then((r) => { if (!r.ok) throw new Error(); return r.json(); })
      .then((d) => { setArmed(Boolean(d.state?.armed)); setSync("D1 SYNCED"); })
      .catch(() => setSync("LOCAL DEMO"));
  }, []);

  const toggle = async () => {
    const next = !armed;
    setArmed(next);
    try {
      const r = await fetch("/api/dashboard", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ armed: next }) });
      if (!r.ok) throw new Error();
      setSync("D1 SYNCED");
    } catch { setSync("LOCAL DEMO"); }
  };

  const x = stocks[pick];
  return <main>
    <header><div className="brand"><i>E</i><span><b>EDGESIGNAL</b><small>INTRADAY INTELLIGENCE</small></span></div><div className="market"><em />NSE DEMO · MARKET FEED DEFERRED</div><button aria-pressed={armed} className={armed ? "armed" : ""} onClick={toggle}>{armed ? "PAPER ENGINE ARMED" : "ARM PAPER ENGINE"}</button></header>
    <section className="hero"><div><label>BUILD MODE · RSS INGESTION ONLINE</label><h1>Find the signal<br /><span>before the crowd.</span></h1><p>Social attention, news sentiment and market confirmation—ranked into explainable intraday trades.</p></div><aside><label>PAPER CAPITAL</label><b>₹20,000</b><small>₹0 realised · 0.00% return</small></aside></section>
    <nav><b>COMMAND CENTER</b><span>SOURCE HEALTH</span><span>TRADES</span><span>RESEARCH</span><span>RULES</span></nav>
    <section className="settings card"><div><label>TRADABLE UNIVERSE</label><section className="switch">{["NIFTY 50", "NIFTY 100", "NIFTY 200"].map((n) => <button className={universe === n ? "on" : ""} onClick={() => setUniverse(n)} key={n}>{n}</button>)}</section></div><div><label>RISK PROFILE</label><b className="red">AGGRESSIVE PAPER</b><small>2% risk/trade · 6% daily stop</small></div><div><label>DECISION CLOCK</label><b>5 MINUTES</b><small>Next-candle limit execution</small></div></section>
    <section className="source-strip card"><div><label>RSS PIPELINE</label><b>LIVE-VERIFIED</b></div><div><label>LAST INGEST TEST</label><b>70 SYMBOL EVENTS</b></div><div><label>STORAGE</label><b>HEADLINES + URLS ONLY</b></div><div><label>BROKER DATA</label><b className="pending">DEFERRED</b></div></section>
    <section className="grid"><div className="card"><div className="title"><span><b>RANKED OPPORTUNITIES</b><small>Market-confirmed simulated snapshot</small></span><em>4 DEMO</em></div><div className="cols"><span>SYMBOL</span><span>SIGNAL</span><span>MOVE</span><span>SCORE</span></div>{stocks.map((a, i) => <button className={`stock ${pick === i ? "selected" : ""}`} onClick={() => setPick(i)} key={a.s}><span><b>{a.s}</b><small>LIQUID · INTRADAY</small></span><b className={a.side.toLowerCase()}>{a.side}</b><span>{a.move}</span><strong>{a.score}</strong></button>)}</div>
      <div className="card detail"><div className="title"><span><b>WHY {x.s}?</b><small>Signal anatomy</small></span><em className={x.side.toLowerCase()}>{x.side}</em></div>{[["PRICE + VOLUME", 88], ["SENTIMENT", 78], ["ATTENTION VELOCITY", 91], ["SOURCE QUALITY", 72], ["MARKET REGIME", 66]].map(([n, v]) => <div className="factor" key={n as string}><span>{n}</span><i><b style={{ width: `${v}%` }} /></i><strong>{v}</strong></div>)}<div className="thesis"><label>MACHINE THESIS</label><p>{x.why}</p></div><div className="order"><span>ENTRY<b>₹979.40</b></span><span>STOP<b>₹970.20</b></span><span>TARGET<b>₹997.80</b></span><span>SIZE<b>21 sh.</b></span></div></div>
      <div className="card sources"><div className="title"><span><b>SOURCE HEALTH</b><small>News + blogs connected · Reddit adapter ready</small></span><em>8 ACTIVE</em></div>{feeds.map((f) => <div className="feed" key={f[0]}><span><b>{f[0]}</b><small>{f[1]}</small></span><strong className={f[2] === "CONNECTED" ? "ok" : "pending"}>{f[2]}</strong></div>)}</div>
      <div className="card risk"><div className="title"><span><b>RISK GUARD</b><small>Independent of strategy logic</small></span><em>READY</em></div><strong>₹400</strong><label>MAX RISK / TRADE</label><section><span>Daily stop<b>₹1,200</b></span><span>Max positions<b>3</b></span><span>Trade cap<b>12/day</b></span><span>Square-off<b>15:15</b></span></section><p>⚠ Paper profile is intentionally aggressive. Live limits require a separate approval gate.</p></div></section>
    <footer>RSS CONNECTORS <b>LIVE-VERIFIED</b> · ORDER ROUTER <b>PAPER</b> · STATE <b>{sync}</b> · MODEL <b>v0.2</b><span>Illustrative signals—not investment advice.</span></footer>
  </main>;
}

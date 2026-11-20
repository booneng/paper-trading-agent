#!/usr/bin/env python3
"""
Paper Trading Agent v2.1 - long & short, crypto + forex + commodities, self-reviewing
====================================================================================
Trades with $1,000 of PAPER money on LIVE hourly prices. No real orders, no
account, no API key. Pure Python standard library (Python 3.8+).

Markets
-------
  Crypto      BTC, ETH, SOL (vs USD)          - Coinbase public market data
  Forex       EUR/USD, GBP/USD, AUD/USD, NZD/USD - Yahoo Finance
  Commodities Gold, Silver, WTI crude oil, Copper (front-month futures) - Yahoo Finance
Each asset class has its own trading costs and leverage (see INSTRUMENTS).
Shorts pay a borrow fee on crypto; forex swap and futures roll costs are ignored.

What it does, 24/7
------------------
1. TRADES long AND short on hourly candles with a trend-following strategy:
   long when the fast EMA crosses above the slow EMA in an uptrend, short when it
   crosses below in a downtrend.
2. WRITES DOWN WHY before every trade (setup, market conditions, plan) -> journal.md
3. STUDIES EVERY CLOSED TRADE: best/worst excursion, why it won or lost, which entry
   conditions contributed, and 12h after the exit whether the exit was right
   -> journal.md, trades.jsonl
4. LEARNS daily: groups trades by cause, side (long/short) and asset class, then
   re-tests small strategy changes on 90 days of real prices; a change is adopted
   only if it beats the current settings on training data AND on the most recent
   30 days it was not tuned on. Max one change per day -> strategy_changelog.md
5. REPORTS daily -> reports/YYYY-MM-DD.md

params.json is re-read every cycle (edit it any time; "locked" stops the tuner
touching a value; "disabled_instruments" switches markets off; "allow_longs" /
"allow_shorts" switch sides off). If this file is replaced with a new version, the
running agent restarts itself to load it.

Commands
--------
  python3 paper_agent.py run [--once] | status | learn | check | reset
  python3 paper_agent.py backtest [--days 60] [--simulate] [--journal]

For learning and experimentation only - not financial advice.
"""

import argparse
import http.cookiejar
import json
import os
import random
import ssl
import sys
import time
import traceback
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone

VERSION = "2.2"
HERE = os.path.dirname(os.path.abspath(__file__))


def P(*a):
    return os.path.join(HERE, *a)


STATE_FILE = P("state.json")
PARAMS_FILE = P("params.json")
TRADES_FILE = P("trades.jsonl")
JOURNAL_FILE = P("journal.md")
CHANGELOG_FILE = P("strategy_changelog.md")
REPORTS_DIR = P("reports")

# fee/slip are fractions of notional per fill; lev = max leverage; borrow_apr only for shorts
INSTRUMENTS = {
    "BTC-USD": {"name": "Bitcoin", "cls": "crypto", "src": "coinbase", "fee": 0.001, "slip": 0.0005, "lev": 1, "borrow_apr": 0.10, "sim": (90000, 0.007)},
    "ETH-USD": {"name": "Ethereum", "cls": "crypto", "src": "coinbase", "fee": 0.001, "slip": 0.0005, "lev": 1, "borrow_apr": 0.10, "sim": (3000, 0.008)},
    "SOL-USD": {"name": "Solana", "cls": "crypto", "src": "coinbase", "fee": 0.001, "slip": 0.0005, "lev": 1, "borrow_apr": 0.10, "sim": (140, 0.010)},
    "EURUSD=X": {"name": "EUR/USD", "cls": "forex", "src": "yahoo", "fee": 0.0, "slip": 0.0001, "lev": 10, "borrow_apr": 0.0, "sim": (1.08, 0.0012)},
    "GBPUSD=X": {"name": "GBP/USD", "cls": "forex", "src": "yahoo", "fee": 0.0, "slip": 0.00012, "lev": 10, "borrow_apr": 0.0, "sim": (1.27, 0.0013)},
    "AUDUSD=X": {"name": "AUD/USD", "cls": "forex", "src": "yahoo", "fee": 0.0, "slip": 0.00015, "lev": 10, "borrow_apr": 0.0, "sim": (0.66, 0.0015)},
    "NZDUSD=X": {"name": "NZD/USD", "cls": "forex", "src": "yahoo", "fee": 0.0, "slip": 0.0002, "lev": 10, "borrow_apr": 0.0, "sim": (0.60, 0.0016)},
    "GC=F": {"name": "Gold", "cls": "commodity", "src": "yahoo", "fee": 0.0002, "slip": 0.0002, "lev": 5, "borrow_apr": 0.0, "sim": (2600, 0.0025)},
    "SI=F": {"name": "Silver", "cls": "commodity", "src": "yahoo", "fee": 0.0002, "slip": 0.0004, "lev": 5, "borrow_apr": 0.0, "sim": (31, 0.0045)},
    "CL=F": {"name": "Crude oil", "cls": "commodity", "src": "yahoo", "fee": 0.0002, "slip": 0.0004, "lev": 5, "borrow_apr": 0.0, "sim": (70, 0.0050)},
    "HG=F": {"name": "Copper", "cls": "commodity", "src": "yahoo", "fee": 0.0002, "slip": 0.0004, "lev": 5, "borrow_apr": 0.0, "sim": (4.2, 0.0035)},
}

SETTINGS = {
    "starting_cash": 1000.0,
    "symbols": list(INSTRUMENTS),
    "granularity": 3600,         # hourly candles
    "poll_seconds": 60,
    "min_order_usd": 10.0,
    "max_open_positions": 5,
    "max_drawdown_halt": 0.20,   # stop opening trades 20% below start
    "warmup": 160,
    "window": 300,
    "followup_bars": 12,
    "learn_every_hours": 24,
    "learn_days": 90,
    "learn_margin": 0.25,
}

DEFAULT_PARAMS = {
    "version": 1,
    "locked": [],
    "allow_longs": True,
    "allow_shorts": True,
    "disabled_instruments": [],
    "ema_fast": 12,
    "ema_slow": 26,
    "ema_trend": 100,
    "cross_lookback": 3,
    "rsi_min": 45,          # RSI measured in the trade's direction (for shorts: 100 - RSI)
    "rsi_max": 70,
    "min_er": 0.0,
    "max_ext_atr": 99.0,
    "min_vol_ratio": 0.0,
    "stop_atr": 2.0,
    "take_profit_atr": 4.0,
    "trail_atr": 2.5,
    "risk_per_trade": 0.0075,
    "max_position_pct": 0.33,   # max margin per position as share of equity
}

TUNE_GRID = {
    "stop_atr": [1.5, 2.0, 2.5, 3.0, 3.5],
    "take_profit_atr": [3.0, 4.0, 5.0, 6.0, 8.0],
    "trail_atr": [2.0, 2.5, 3.0, 3.5, 4.0],
    "rsi_min": [40, 45, 50, 55],
    "rsi_max": [65, 70, 75, 80],
    "min_er": [0.0, 0.1, 0.2, 0.3, 0.4],
    "max_ext_atr": [1.5, 2.0, 2.5, 3.0, 99.0],
    "min_vol_ratio": [0.0, 0.8, 1.0, 1.2],
    "ema_trend": [50, 100, 150],
    "cross_lookback": [1, 3, 5],
}

LABEL = {
    "stop_atr": "stop-loss distance (ATR)", "take_profit_atr": "profit target (ATR)",
    "trail_atr": "trailing stop distance (ATR)", "rsi_min": "minimum directional RSI to enter",
    "rsi_max": "maximum directional RSI to enter", "min_er": "minimum trend efficiency (choppiness filter)",
    "max_ext_atr": "max distance from slow EMA (late-entry filter)", "min_vol_ratio": "minimum volume vs average",
    "ema_trend": "trend EMA length", "cross_lookback": "bars allowed since the EMA cross",
}

PARAM_TAGS = {
    "min_er": ["choppy"], "max_ext_atr": ["extended"], "rsi_max": ["overbought", "oversold"],
    "min_vol_ratio": ["weak_volume"], "stop_atr": ["shaken_out", "immediate_reversal"],
    "trail_atr": ["gave_back"], "take_profit_atr": ["exited_early", "clean_win"],
    "ema_trend": ["against_market"], "cross_lookback": ["extended"], "rsi_min": [],
}

TAG_TEXT = {
    "clean_win": "hit the profit target",
    "immediate_reversal": "reversed right after entry",
    "gave_back": "gave back a large open profit",
    "shaken_out": "stopped out, then price recovered",
    "exited_early": "kept moving our way after exit",
    "good_exit": "exit avoided a further adverse move",
    "choppy": "entered in a choppy market",
    "extended": "entered late / overextended",
    "overbought": "long entered with RSI > 65",
    "oversold": "short entered with RSI < 35",
    "weak_volume": "entered on weak volume",
    "against_market": "most of its asset class trended the other way",
    "long": "all long trades", "short": "all short trades",
    "crypto": "all crypto trades", "forex": "all forex trades", "commodity": "all commodity trades",
}
GROUP_TAGS = ("long", "short", "crypto", "forex", "commodity")


# --------------------------------------------------------------------------- utils
def log(msg):
    print(f"[{datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')} UTC] {msg}", flush=True)


def now_iso():
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")


def ts_iso(t):
    return datetime.fromtimestamp(t, timezone.utc).strftime("%Y-%m-%d %H:%M UTC")


def write_json(path, obj):
    tmp = path + ".tmp"
    with open(tmp, "w") as f:
        json.dump(obj, f, indent=2)
    os.replace(tmp, path)


def append(path, text):
    with open(path, "a") as f:
        f.write(text)


def fmt_px(x):
    return f"{x:,.2f}" if x >= 100 else f"{x:,.4f}" if x >= 1 else f"{x:.5f}"


def name(sym):
    return INSTRUMENTS.get(sym, {}).get("name", sym)


# --------------------------------------------------------------------------- indicators
def ema_s(v, n):
    k = 2.0 / (n + 1)
    out = [v[0]]
    for x in v[1:]:
        out.append(out[-1] + k * (x - out[-1]))
    return out


def rsi_s(c, n=14):
    out = [50.0] * len(c)
    if len(c) <= n:
        return out
    g = l = 0.0
    for i in range(1, n + 1):
        d = c[i] - c[i - 1]
        g += max(d, 0.0)
        l += max(-d, 0.0)
    ag, al = g / n, l / n

    def val(ag, al):
        return 100.0 if al == 0 else 100.0 - 100.0 / (1 + ag / al)
    out[n] = val(ag, al)
    for i in range(n + 1, len(c)):
        d = c[i] - c[i - 1]
        ag = (ag * (n - 1) + max(d, 0.0)) / n
        al = (al * (n - 1) + max(-d, 0.0)) / n
        out[i] = val(ag, al)
    return out


def atr_s(cs, n=14):
    out, a, run = [], 0.0, 0.0
    for i, c in enumerate(cs):
        if i == 0:
            tr = c["high"] - c["low"]
        else:
            pc = cs[i - 1]["close"]
            tr = max(c["high"] - c["low"], abs(c["high"] - pc), abs(c["low"] - pc))
        if i < n:
            run += tr
            a = run / (i + 1)
        else:
            a = (a * (n - 1) + tr) / n
        out.append(a)
    return out


def er_s(c, n=20):
    """Kaufman efficiency ratio: 1 = straight-line trend, ~0 = pure chop."""
    out = [0.0] * len(c)
    noise = 0.0
    diffs = [0.0] + [abs(c[i] - c[i - 1]) for i in range(1, len(c))]
    for i in range(1, len(c)):
        noise += diffs[i]
        if i > n:
            noise -= diffs[i - n]
        if i >= n and noise > 0:
            out[i] = abs(c[i] - c[i - n]) / noise
    return out


def sma_s(v, n=20):
    out, run = [], 0.0
    for i, x in enumerate(v):
        run += x
        if i >= n:
            run -= v[i - n]
        out.append(run / min(i + 1, n))
    return out


def compute(cs, p):
    closes = [c["close"] for c in cs]
    return {
        "fast": ema_s(closes, int(p["ema_fast"])),
        "slow": ema_s(closes, int(p["ema_slow"])),
        "trend": ema_s(closes, int(p["ema_trend"])),
        "rsi": rsi_s(closes, 14),
        "atr": atr_s(cs, 14),
        "er": er_s(closes, 20),
        "vavg": sma_s([c.get("vol", 0.0) for c in cs], 20),
    }


# --------------------------------------------------------------------------- params & state
def load_params():
    p = dict(DEFAULT_PARAMS)
    if os.path.exists(PARAMS_FILE):
        try:
            with open(PARAMS_FILE) as f:
                p.update(json.load(f))
        except (ValueError, OSError) as e:
            log(f"! params.json unreadable ({e}); using defaults")
    return p


def new_state(settings):
    return {"created": now_iso(), "agent_version": VERSION,
            "starting_cash": settings["starting_cash"], "cash": settings["starting_cash"],
            "positions": {}, "followups": [], "last_candle": {}, "last_prices": {},
            "next_check": {}, "src_pref": {}, "yahoo": {}, "equity_history": [], "skipped": {}, "last_learn": 0, "next_id": 1}


def load_state():
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE) as f:
            s = json.load(f)
        for k, v in new_state(SETTINGS).items():
            s.setdefault(k, v)
        for p in s["positions"].values():          # positions opened by v2.0 (long, unleveraged)
            p.setdefault("side", "long")
            p.setdefault("dir", 1)
            p.setdefault("margin", p.get("cost", p["qty"] * p["entry"]))
            p.setdefault("notional", p["qty"] * p["entry"])
            p.setdefault("entry_fee", p.get("cost", 0) - p["qty"] * p["entry"])
        return s
    return new_state(SETTINGS)


def load_trades(path=TRADES_FILE):
    out = []
    if os.path.exists(path):
        with open(path) as f:
            for line in f:
                line = line.strip()
                if line:
                    out.append(json.loads(line))
    return out


# --------------------------------------------------------------------------- the agent
class Agent:
    def __init__(self, settings, params, state, trades_path=None, journal_path=None, verbose=False):
        self.cfg, self.p, self.s = settings, params, state
        self.trades_path, self.journal_path, self.verbose = trades_path, journal_path, verbose
        self.closed = load_trades(trades_path) if trades_path else []
        self.flags = {}

    # ---- accounting: every position holds margin; value = margin + unrealized P&L
    @staticmethod
    def pos_value(pos, price):
        return pos["margin"] + pos["dir"] * (price - pos["entry"]) * pos["qty"]

    def equity(self, prices=None):
        prices = prices or self.s["last_prices"]
        return self.s["cash"] + sum(self.pos_value(p, prices.get(sym, p["entry"]))
                                    for sym, p in self.s["positions"].items())

    def halted(self, prices):
        return self.equity(prices) < self.s["starting_cash"] * (1 - self.cfg["max_drawdown_halt"])

    def _skip(self, why):
        self.s["skipped"][why] = self.s["skipped"].get(why, 0) + 1

    # ---- one newly closed candle cs[i] for sym
    def step(self, sym, cs, i, S, prices):
        c, a = cs[i], S["atr"][i]
        if i < self.cfg["warmup"] or a <= 0:
            return
        self.flags[sym] = c["close"] > S["trend"][i]
        self._followups(sym, c)
        pos = self.s["positions"].get(sym)
        if pos:
            self._manage(sym, pos, c, S, i)
            return
        p = self.p
        f, sl = S["fast"], S["slow"]
        side, ago = None, None
        for k in range(int(p["cross_lookback"])):
            j = i - k
            if f[j - 1] <= sl[j - 1] and f[j] > sl[j]:
                side, ago = "long", k
                break
            if f[j - 1] >= sl[j - 1] and f[j] < sl[j]:
                side, ago = "short", k
                break
        if side is None:
            return
        d = 1 if side == "long" else -1
        if d * (f[i] - sl[i]) <= 0 or d * (c["close"] - S["trend"][i]) <= 0:
            return
        if sym in p.get("disabled_instruments", []):
            return
        if (side == "long" and not p.get("allow_longs", True)) or (side == "short" and not p.get("allow_shorts", True)):
            self._skip(f"{side}s_disabled")
            return
        if self.halted(prices):
            self._skip("drawdown_halt")
            return
        if len(self.s["positions"]) >= self.cfg["max_open_positions"]:
            self._skip("max_positions")
            return
        feats = self._features(sym, cs, i, S, ago, d)
        blockers = []
        if not (p["rsi_min"] < feats["rsi"] < p["rsi_max"]):
            blockers.append("rsi")
        if feats["er"] < p["min_er"]:
            blockers.append("choppy")
        if feats["ext_atr"] > p["max_ext_atr"]:
            blockers.append("extended")
        if feats["vol_ratio"] < p["min_vol_ratio"]:
            blockers.append("weak_volume")
        if blockers:
            for b in blockers:
                self._skip(b)
            return
        self._open(sym, side, c, a, feats, prices)

    def _features(self, sym, cs, i, S, ago, d):
        c, a = cs[i], S["atr"][i]
        vavg = S["vavg"][i]
        cls = INSTRUMENTS[sym]["cls"]
        peers = [s for s in self.flags if INSTRUMENTS.get(s, {}).get("cls") == cls]
        with_us = sum(1 for s in peers if self.flags[s] == (d == 1)) / len(peers) if peers else 1.0
        raw = S["rsi"][i]
        return {
            "rsi": round(raw if d == 1 else 100 - raw, 1),     # directional
            "rsi_raw": round(raw, 1),
            "er": round(S["er"][i], 3),
            "ext_atr": round(d * (c["close"] - S["slow"][i]) / a, 2),
            "trend_slope": round(d * (S["trend"][i] / S["trend"][i - 10] - 1) * 100, 3),
            "vol_ratio": round(c.get("vol", 0.0) / vavg, 2) if vavg > 0 else 1.0,
            "atr_pct": round(a / c["close"] * 100, 3),
            "breadth": round(with_us, 2),
            "cross_ago": ago,
        }

    # ---- entries
    def _open(self, sym, side, c, a, feats, prices):
        cfg, p, I = self.cfg, self.p, INSTRUMENTS[sym]
        d = 1 if side == "long" else -1
        fill = c["close"] * (1 + d * I["slip"])
        stop = fill - d * p["stop_atr"] * a
        tp = fill + d * p["take_profit_atr"] * a
        eq = self.equity(prices)
        notional = min(eq * p["risk_per_trade"] / (p["stop_atr"] * a) * fill,
                       eq * p["max_position_pct"] * I["lev"])
        cash = self.s["cash"]
        if notional / I["lev"] + notional * I["fee"] > cash:
            notional = cash / (1.0 / I["lev"] + I["fee"]) * 0.999
        if notional < cfg["min_order_usd"]:
            self._skip("no_cash")
            return
        qty = notional / fill
        margin = notional / I["lev"]
        fee = notional * I["fee"]
        self.s["cash"] -= margin + fee
        tid = self.s["next_id"]
        self.s["next_id"] += 1
        thesis = self._thesis(sym, side, feats)
        risk = qty * p["stop_atr"] * a + 2 * fee
        pos = {"id": tid, "symbol": sym, "side": side, "dir": d, "opened_t": c["t"], "entry": fill,
               "qty": qty, "notional": notional, "margin": margin, "entry_fee": fee,
               "stop": stop, "init_stop": stop, "tp": tp, "atr": a, "risk_usd": risk,
               "features": feats, "thesis": thesis, "params_version": p.get("version", 1),
               "mfe": 0.0, "mae": 0.0, "bars": 0}
        self.s["positions"][sym] = pos
        verb = "Bought" if d == 1 else "Sold short"
        if self.verbose:
            log(f">> {side.upper():5} #{tid} {name(sym)} {qty:.6g} @ {fmt_px(fill)} - {thesis}")
        lev_txt = f", {I['lev']}x leverage, margin ${margin:,.2f}" if I["lev"] > 1 else ""
        self._journal(
            f"\n## #{tid} OPEN {side.upper()} {name(sym)} - {ts_iso(c['t'])}\n"
            f"**{verb}** {qty:.6g} @ {fmt_px(fill)} (${notional:,.2f} exposure{lev_txt}, strategy v{pos['params_version']})\n\n"
            f"**Why:** {thesis}\n\n"
            f"**Plan:** stop {fmt_px(stop)} ({'-' if d == 1 else '+'}{p['stop_atr']} ATR), target {fmt_px(tp)} "
            f"({'+' if d == 1 else '-'}{p['take_profit_atr']} ATR), trailing {p['trail_atr']} ATR. "
            f"Risking about ${risk:.2f} ({risk / eq * 100:.1f}% of equity).\n")

    def _thesis(self, sym, side, f):
        cls = INSTRUMENTS[sym]["cls"]
        when = "on this candle" if f["cross_ago"] == 0 else f"{f['cross_ago']}h ago"
        er_word = "clean trend" if f["er"] >= 0.4 else "moderate trend" if f["er"] >= 0.2 else "choppy"
        if side == "long":
            setup = (f"{name(sym)}: fast EMA crossed ABOVE the slow EMA {when}, price above the trend EMA "
                     f"(trend EMA slope {f['trend_slope']:+.2f}%/10h)")
            ext = f"{f['ext_atr']:.1f} ATR above the slow EMA"
            mkt = f"{f['breadth'] * 100:.0f}% of {cls} in uptrends"
        else:
            setup = (f"{name(sym)}: fast EMA crossed BELOW the slow EMA {when}, price below the trend EMA "
                     f"(trend EMA slope {-f['trend_slope']:+.2f}%/10h)")
            ext = f"{f['ext_atr']:.1f} ATR below the slow EMA"
            mkt = f"{f['breadth'] * 100:.0f}% of {cls} in downtrends"
        vol = (f", volume {f['vol_ratio']:.1f}x average" if INSTRUMENTS[sym]["cls"] != "forex" else "")
        return (f"{setup}. RSI {f['rsi_raw']:.0f}, trend efficiency {f['er']:.2f} ({er_word}), price {ext}"
                f"{vol}, {mkt}, hourly volatility {f['atr_pct']:.2f}%.")

    # ---- open position management
    def _manage(self, sym, pos, c, S, i):
        d, a0 = pos["dir"], pos["atr"]
        pos["bars"] += 1
        fav = (c["high"] - pos["entry"]) if d == 1 else (pos["entry"] - c["low"])
        adv = (pos["entry"] - c["low"]) if d == 1 else (c["high"] - pos["entry"])
        pos["mfe"] = max(pos["mfe"], fav / a0)
        pos["mae"] = max(pos["mae"], adv / a0)
        f, sl = S["fast"], S["slow"]
        stop_hit = c["low"] <= pos["stop"] if d == 1 else c["high"] >= pos["stop"]
        tp_hit = c["high"] >= pos["tp"] if d == 1 else c["low"] <= pos["tp"]
        reversal = (d * (f[i] - sl[i]) < 0) and (d * (f[i - 1] - sl[i - 1]) >= 0)
        exit_px, code = None, None
        if stop_hit:   # checked first: conservative when stop and target are both inside one candle
            exit_px = min(pos["stop"], c["open"]) if d == 1 else max(pos["stop"], c["open"])
            code = "trailing_stop" if d * (pos["stop"] - pos["init_stop"]) > 1e-12 else "stop_loss"
        elif tp_hit:
            exit_px = max(pos["tp"], c["open"]) if d == 1 else min(pos["tp"], c["open"])
            code = "target"
        elif reversal:
            exit_px, code = c["close"], "trend_reversal"
        if exit_px is not None:
            self._close(sym, pos, exit_px, code, c["t"])
        elif d == 1:
            pos["stop"] = max(pos["stop"], c["close"] - self.p["trail_atr"] * S["atr"][i])
        else:
            pos["stop"] = min(pos["stop"], c["close"] + self.p["trail_atr"] * S["atr"][i])

    def _close(self, sym, pos, px, code, t):
        I, d = INSTRUMENTS[sym], pos["dir"]
        del self.s["positions"][sym]
        fill = px * (1 - d * I["slip"])
        gross = d * (fill - pos["entry"]) * pos["qty"]
        fee = pos["qty"] * fill * I["fee"]
        hours = pos["bars"] * self.cfg["granularity"] / 3600
        borrow = pos["notional"] * I["borrow_apr"] * hours / 8760 if d == -1 else 0.0
        self.s["cash"] += pos["margin"] + gross - fee - borrow
        pnl = gross - fee - borrow - pos["entry_fee"]
        r = pnl / pos["risk_usd"] if pos["risk_usd"] > 0 else 0.0
        exit_move = d * (fill - pos["entry"]) / pos["atr"]
        verdict, tags = self._post_mortem(sym, pos, code, pnl, exit_move)
        tr = {"id": pos["id"], "symbol": sym, "name": name(sym), "cls": I["cls"], "side": pos["side"],
              "opened": ts_iso(pos["opened_t"]), "closed": ts_iso(t), "closed_t": t,
              "entry": round(pos["entry"], 6), "exit": round(fill, 6), "qty": round(pos["qty"], 8),
              "pnl": round(pnl, 4), "r": round(r, 2), "win": pnl > 0, "exit_reason": code, "hours": hours,
              "borrow_cost": round(borrow, 4), "mfe_atr": round(pos["mfe"], 2), "mae_atr": round(pos["mae"], 2),
              "exit_move_atr": round(exit_move, 2), "features": pos["features"], "thesis": pos["thesis"],
              "verdict": verdict, "tags": tags, "followup": None, "params_version": pos["params_version"]}
        self.closed.append(tr)
        self._save_trades()
        self.s["followups"].append({"id": pos["id"], "symbol": sym, "dir": d, "exit_t": t, "exit_px": fill,
                                    "entry": pos["entry"], "atr": pos["atr"], "code": code,
                                    "win": pnl > 0, "bars": 0, "hi": fill, "lo": fill})
        if self.verbose:
            log(f">> CLOSE #{pos['id']} {pos['side']} {name(sym)} @ {fmt_px(fill)} ({code.replace('_', ' ')}) "
                f"P&L {pnl:+.2f} ({r:+.2f}R) - {verdict}")
        extra = f" (incl. ${borrow:.2f} short borrow fee)" if borrow > 0.005 else ""
        self._journal(
            f"\n## #{pos['id']} CLOSE {pos['side'].upper()} {name(sym)} - {ts_iso(t)}\n"
            f"**Result:** {'WIN' if pnl > 0 else 'LOSS'} {pnl:+.2f} USD ({r:+.2f}R){extra} after {hours:.0f}h, "
            f"exit by {code.replace('_', ' ')} @ {fmt_px(fill)} (entry {fmt_px(pos['entry'])})\n\n"
            f"**What happened:** best point +{pos['mfe']:.1f} ATR in our favour, worst -{pos['mae']:.1f} ATR "
            f"against, exited at {exit_move:+.1f} ATR.\n\n"
            f"**Why it {'worked' if pnl > 0 else 'failed'}:** {verdict}\n\n"
            f"**Tags:** {', '.join(tags)}\n")

    def _post_mortem(self, sym, pos, code, pnl, exit_move):
        f, mfe, side = pos["features"], pos["mfe"], pos["side"]
        cls = INSTRUMENTS[sym]["cls"]
        move = "rise" if side == "long" else "fall"
        tags = []
        if pnl > 0:
            if code == "target":
                v = f"The thesis played out: the {'up' if side == 'long' else 'down'}trend carried price to the target."
                tags.append("clean_win")
            elif code == "trailing_stop":
                v = f"The trend ran +{mfe:.1f} ATR our way and the trailing stop locked in part of it"
                if mfe - exit_move > 2.0:
                    v += f", but {mfe - exit_move:.1f} ATR of open profit was given back."
                    tags.append("gave_back")
                else:
                    v += "."
            else:
                v = "Momentum faded (EMAs crossed back) and the trade was closed while still in profit."
        else:
            if mfe < 0.5:
                v = f"The setup never worked: instead of continuing to {move}, price turned against the trade almost immediately."
                tags.append("immediate_reversal")
            elif mfe >= 1.5:
                v = f"It was +{mfe:.1f} ATR in profit but the gain was lost - the exits were too loose to protect it."
                tags.append("gave_back")
            else:
                v = f"It moved only +{mfe:.1f} ATR our way before failing."
            if code == "trend_reversal":
                v += " Closed early when momentum reversed, which kept the loss small."
        # entry conditions are tagged on EVERY trade (wins too) so win rates compare fairly
        factors = []
        if f["er"] < 0.2:
            tags.append("choppy")
            factors.append(f"the market was choppy (trend efficiency {f['er']:.2f})")
        if f["ext_atr"] > 2.0:
            tags.append("extended")
            factors.append(f"entry was late, {f['ext_atr']:.1f} ATR beyond the slow EMA")
        if f["rsi"] > 65:
            tags.append("overbought" if side == "long" else "oversold")
            factors.append(f"RSI was already {'high' if side == 'long' else 'low'} ({f['rsi_raw']:.0f})")
        if f["vol_ratio"] < 0.8 and cls != "forex":
            tags.append("weak_volume")
            factors.append(f"volume was weak ({f['vol_ratio']:.1f}x average)")
        if f["breadth"] < 0.5:
            tags.append("against_market")
            factors.append(f"most other {cls} instruments were trending the other way")
        if factors:
            v += (" Likely contributors: " if pnl <= 0 else " It won despite: ") + "; ".join(factors) + "."
        elif pnl <= 0:
            v += " Entry conditions looked healthy, so this is likely normal noise - a loss the strategy expects to take."
        tags += [side, cls]
        return v, tags

    def _followups(self, sym, c):
        keep = []
        for fu in self.s["followups"]:
            if fu["symbol"] != sym or c["t"] <= fu["exit_t"]:
                keep.append(fu)
                continue
            fu["bars"] += 1
            fu["hi"], fu["lo"] = max(fu["hi"], c["high"]), min(fu["lo"], c["low"])
            if fu["bars"] < self.cfg["followup_bars"]:
                keep.append(fu)
                continue
            a, d = fu["atr"], fu.get("dir", 1)
            up = (fu["hi"] - fu["exit_px"]) / a
            down = (fu["exit_px"] - fu["lo"]) / a
            our_way, against = (up, down) if d == 1 else (down, up)
            tag, note = None, (f"In the {fu['bars']}h after exit price moved up to {our_way:.1f} ATR further in "
                               f"the trade's direction and {against:.1f} ATR against it.")
            recovered = fu["hi"] >= fu["entry"] + a if d == 1 else fu["lo"] <= fu["entry"] - a
            if fu["code"] == "stop_loss" and recovered:
                tag = "shaken_out"
                note += " After the stop, price went well past the entry in our direction: the stop was likely too tight."
            elif fu["win"] and our_way >= 2.0:
                tag = "exited_early"
                note += " The move kept going after the exit: the exit was early."
            elif against >= 2.0:
                tag = "good_exit"
                note += " Price moved further against the position after the exit: getting out was right."
            else:
                note += " No strong verdict on the exit."
            for tr in self.closed:
                if tr["id"] == fu["id"]:
                    tr["followup"] = note
                    if tag:
                        tr["tags"].append(tag)
            self._save_trades()
            self._journal(f"\n## #{fu['id']} FOLLOW-UP {name(fu['symbol'])}\n{note}{' Tag: ' + tag if tag else ''}\n")
        self.s["followups"] = keep

    def _save_trades(self):
        if self.trades_path:
            tmp = self.trades_path + ".tmp"
            with open(tmp, "w") as f:
                for tr in self.closed:
                    f.write(json.dumps(tr) + "\n")
            os.replace(tmp, self.trades_path)

    def _journal(self, text):
        if self.journal_path:
            append(self.journal_path, text)


# --------------------------------------------------------------------------- market data
_SSL = ssl.create_default_context()
for _ca in ("/etc/ssl/cert.pem", "/private/etc/ssl/cert.pem"):
    if os.path.exists(_ca):
        try:
            _SSL.load_verify_locations(_ca)
        except Exception:
            pass
        break

UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"


def _get_json(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=20, context=_SSL) as r:
        return json.load(r)


def fetch_coinbase(sym, gran, start=None, end=None):
    url = f"https://api.exchange.coinbase.com/products/{sym}/candles?granularity={gran}"
    if start is not None and end is not None:
        def fmt(x):
            return datetime.fromtimestamp(x, timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        url += f"&start={fmt(start)}&end={fmt(end)}"
    rows = _get_json(url)
    cs = [{"t": int(r[0]), "low": float(r[1]), "high": float(r[2]), "open": float(r[3]),
           "close": float(r[4]), "vol": float(r[5])} for r in rows]
    cs.sort(key=lambda c: c["t"])
    return cs


# Data sources per market, in order of preference. The last source that worked is kept
# ("sticky") so a market's price series does not jump between sources.
SOURCES = {
    "BTC-USD": [("coinbase", "BTC-USD")],
    "ETH-USD": [("coinbase", "ETH-USD")],
    "SOL-USD": [("coinbase", "SOL-USD")],
    "EURUSD=X": [("yahoo", "EURUSD=X"), ("kraken", "EURUSD")],
    "GBPUSD=X": [("yahoo", "GBPUSD=X"), ("kraken", "GBPUSD")],
    "AUDUSD=X": [("yahoo", "AUDUSD=X"), ("kraken", "AUDUSD")],
    "NZDUSD=X": [("yahoo", "NZDUSD=X")],
    "GC=F": [("yahoo", "GC=F"), ("coinbase", "PAXG-USD")],   # PAXG: gold-backed token, tracks spot gold
    "SI=F": [("yahoo", "SI=F")],
    "CL=F": [("yahoo", "CL=F")],
    "HG=F": [("yahoo", "HG=F")],
}
SRC_PREF = {}      # market -> index into SOURCES of the last source that worked
YAHOO = {"opener": None, "crumb": None, "block_until": 0.0, "backoff": 900.0}


try:                                   # optional: imitates Chrome's TLS fingerprint, which Yahoo
    from curl_cffi import requests as _cffi   # increasingly requires (pip install curl_cffi)
except Exception:
    _cffi = None


class _CffiOpener:
    """Make a curl_cffi session look like a urllib opener."""
    def __init__(self):
        self.s = _cffi.Session(impersonate="chrome")

    def open(self, req, timeout=20):
        url = req.full_url if hasattr(req, "full_url") else req
        r = self.s.get(url, timeout=timeout)
        if r.status_code >= 400:
            raise urllib.error.HTTPError(url, r.status_code, str(r.reason or ""), {}, None)
        import io
        return io.BytesIO(r.content)


def _yahoo_opener():
    """Browser-like session: get Yahoo's consent cookie and a 'crumb' token first."""
    if YAHOO["opener"] is None:
        if _cffi is not None:
            op = _CffiOpener()
        else:
            jar = http.cookiejar.CookieJar()
            op = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar),
                                             urllib.request.HTTPSHandler(context=_SSL))
        hdr = {"User-Agent": UA, "Accept-Language": "en-US,en;q=0.9"}
        for url in ("https://fc.yahoo.com", "https://finance.yahoo.com/"):
            try:
                op.open(urllib.request.Request(url, headers=hdr), timeout=15).read(2000)
            except Exception:
                pass
        try:
            r = op.open(urllib.request.Request("https://query1.finance.yahoo.com/v1/test/getcrumb", headers=hdr), timeout=15)
            crumb = r.read().decode().strip()
            YAHOO["crumb"] = crumb if crumb and len(crumb) < 40 and "<" not in crumb else None
        except Exception:
            YAHOO["crumb"] = None
        YAHOO["opener"] = op
    return YAHOO["opener"]


def fetch_yahoo(sym, days):
    if time.time() < YAHOO["block_until"]:
        raise RuntimeError(f"Yahoo is rate-limiting us; paused until {ts_iso(YAHOO['block_until'])}")
    op = _yahoo_opener()
    last_err = None
    for host in ("query2", "query1"):
        url = (f"https://{host}.finance.yahoo.com/v8/finance/chart/{urllib.parse.quote(sym)}"
               f"?interval=1h&range={days}d&includePrePost=false")
        if YAHOO["crumb"]:
            url += "&crumb=" + urllib.parse.quote(YAHOO["crumb"])
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json",
                                                       "Accept-Language": "en-US,en;q=0.9"})
            r = op.open(req, timeout=20)
            data = json.load(r)
            res = (data.get("chart") or {}).get("result") or []
            if not res:
                raise ValueError(f"no data: {(data.get('chart') or {}).get('error')}")
            ts = res[0].get("timestamp") or []
            q = res[0]["indicators"]["quote"][0]
            vols = q.get("volume") or [0] * len(ts)
            out = {}
            for k, t in enumerate(ts):
                o, h, l, c = q["open"][k], q["high"][k], q["low"][k], q["close"][k]
                if None in (o, h, l, c):
                    continue
                out[int(t)] = {"t": int(t), "open": float(o), "high": float(max(h, o, c)),
                               "low": float(min(l, o, c)), "close": float(c), "vol": float(vols[k] or 0)}
            YAHOO["backoff"] = 900.0
            return [out[t] for t in sorted(out)]
        except urllib.error.HTTPError as e:
            last_err = e
            if e.code in (401, 403):
                YAHOO["opener"] = None          # refresh cookie + crumb next time
            if e.code == 429:                   # back off: 15 min, doubling up to 6 h
                YAHOO["block_until"] = time.time() + YAHOO["backoff"]
                YAHOO["backoff"] = min(YAHOO["backoff"] * 2, 6 * 3600)
                YAHOO["opener"] = None
                break
        except Exception as e:
            last_err = e
    raise last_err


def fetch_kraken(pair):
    d = _get_json(f"https://api.kraken.com/0/public/OHLC?pair={pair}&interval=60")
    if d.get("error"):
        raise ValueError(f"Kraken: {d['error']}")
    key = [k for k in d["result"] if k != "last"][0]
    return [{"t": int(r[0]), "open": float(r[1]), "high": float(r[2]), "low": float(r[3]),
             "close": float(r[4]), "vol": float(r[6])} for r in d["result"][key]]


def coinbase_history(sym, gran, days):
    end = int(time.time()) // gran * gran
    start = end - days * 86400
    out, cursor = {}, end
    while cursor > start:
        cs_start = max(start, cursor - 300 * gran)
        for c in fetch_coinbase(sym, gran, cs_start, cursor):
            out[c["t"]] = c
        cursor = cs_start
        time.sleep(0.35)
    return sorted(out.values(), key=lambda c: c["t"])


def closed_only(cs, gran):
    now = time.time()
    return [c for c in cs if c["t"] + gran <= now]


def fetch_any(sym, gran, days, recent):
    """Try the market's sources (last working one first). Returns (closed candles, source label)."""
    srcs = SOURCES[sym]
    pref = SRC_PREF.get(sym, 0)
    errors = []
    for i in [pref] + [j for j in range(len(srcs)) if j != pref]:
        src, ref = srcs[i]
        try:
            if src == "coinbase":
                cs = fetch_coinbase(ref, gran) if recent else coinbase_history(ref, gran, days)
            elif src == "yahoo":
                cs = fetch_yahoo(ref, 30 if recent else days)
            else:
                cs = fetch_kraken(ref)
            cs = closed_only(cs, gran)
            if not cs:
                raise ValueError("no candles")
            if SRC_PREF.get(sym) != i:
                log(f"Data source for {name(sym)}: {src} ({ref})"
                    + (f" - after: {'; '.join(errors)}" if errors else ""))
                SRC_PREF[sym] = i
            return cs, f"{src}:{ref}"
        except Exception as e:
            errors.append(f"{src} failed ({str(e)[:90]})")
    raise RuntimeError("; ".join(errors))


def fetch_recent(sym, gran):
    return fetch_any(sym, gran, 30, True)[0][-SETTINGS["window"]:]


def fetch_history(sym, gran, days):
    return fetch_any(sym, gran, days, False)[0]


def simulate_candles(n, start_price, gran, seed, vol, with_volume=True):
    rng = random.Random(seed)
    t0 = int(time.time()) // gran * gran - n * gran
    price, drift, out = start_price, 0.0, []
    for i in range(n):
        if rng.random() < 0.01:
            drift = rng.choice([-0.25, -0.08, 0.0, 0.0, 0.08, 0.25]) * vol
        o, hi, lo = price, price, price
        for _ in range(6):
            price *= 1 + drift / 6 + vol / 2.45 * rng.gauss(0, 1)
            hi, lo = max(hi, price), min(lo, price)
        v = abs(rng.gauss(100, 30)) * (1 + 0.5 * abs(price / o - 1) / vol) if with_volume else 0.0
        out.append({"t": t0 + i * gran, "open": o, "high": hi, "low": lo, "close": price, "vol": v})
    return out


def get_data(settings, days, simulate=False, seed=7, symbols=None):
    gran = settings["granularity"]
    symbols = symbols or settings["symbols"]
    if simulate:
        n = days * 86400 // gran
        return {s: simulate_candles(n, INSTRUMENTS[s]["sim"][0], gran, seed + k, INSTRUMENTS[s]["sim"][1],
                                    INSTRUMENTS[s]["cls"] != "forex")
                for k, s in enumerate(symbols)}
    data = {}
    for s in symbols:
        try:
            data[s] = fetch_history(s, gran, days)
        except Exception as e:
            log(f"! could not load history for {name(s)}: {e}")
    return {s: cs for s, cs in data.items() if len(cs) > settings["warmup"] + 50}


# --------------------------------------------------------------------------- backtest engine
def run_sim(settings, params, data, t_start=None, t_end=None, journal_path=None, verbose=False):
    state = new_state(settings)
    agent = Agent(settings, params, state, journal_path=journal_path, verbose=verbose)
    series = {s: compute(cs, params) for s, cs in data.items()}
    index = {s: {c["t"]: i for i, c in enumerate(cs)} for s, cs in data.items()}
    times = sorted({c["t"] for cs in data.values() for c in cs})
    prices, curve = {}, []
    for t in times:
        if t_start is not None and t < t_start:
            for s, cs in data.items():
                i = index[s].get(t)
                if i is not None:
                    prices[s] = cs[i]["close"]
                    if i >= settings["warmup"]:
                        agent.flags[s] = cs[i]["close"] > series[s]["trend"][i]
            continue
        if t_end is not None and t >= t_end:
            break
        for s, cs in data.items():
            i = index[s].get(t)
            if i is None:
                continue
            prices[s] = cs[i]["close"]
            agent.step(s, cs, i, series[s], prices)
        curve.append(agent.equity(prices))
    start = settings["starting_cash"]
    final = curve[-1] if curve else start
    peak, mdd = start, 0.0
    for e in curve:
        peak = max(peak, e)
        mdd = max(mdd, (peak - e) / peak)
    closed = agent.closed
    ret = (final / start - 1) * 100
    return {"final": final, "ret": ret, "mdd": mdd * 100, "n": len(closed),
            "win_rate": sum(t["win"] for t in closed) / len(closed) * 100 if closed else 0.0,
            "avg_r": sum(t["r"] for t in closed) / len(closed) if closed else 0.0,
            "score": ret - 0.5 * mdd * 100, "trades": closed, "open": list(state["positions"]),
            "skipped": state["skipped"], "state": state}


# --------------------------------------------------------------------------- learning
def analyse(trades):
    """Group closed trades by cause, side, asset class and entry condition."""
    out = {"n": len(trades), "tags": {}, "features": {}, "lessons": []}
    if not trades:
        out["lessons"].append("No closed trades yet - nothing to learn from live trading so far.")
        return out
    out["win_rate"] = sum(t["win"] for t in trades) / len(trades) * 100
    out["avg_r"] = sum(t["r"] for t in trades) / len(trades)
    out["pnl"] = sum(t["pnl"] for t in trades)
    for t in trades:
        tags = set(t["tags"]) | {t.get("side", "long"), t.get("cls", "crypto")}
        for tag in tags:
            d = out["tags"].setdefault(tag, {"n": 0, "wins": 0, "r": 0.0, "pnl": 0.0})
            d["n"] += 1
            d["wins"] += t["win"]
            d["r"] += t["r"]
            d["pnl"] += t["pnl"]
    for d in out["tags"].values():
        d["win_rate"] = d["wins"] / d["n"] * 100
        d["avg_r"] = d["r"] / d["n"]
    names = {"rsi": "RSI in the trade's direction", "er": "trend efficiency",
             "ext_atr": "distance beyond the slow EMA", "vol_ratio": "volume vs average",
             "breadth": "share of its asset class trending the same way", "trend_slope": "trend slope"}

    def st(g):
        return {"n": len(g), "win_rate": sum(t["win"] for t in g) / len(g) * 100,
                "avg_r": sum(t["r"] for t in g) / len(g)}
    for k, nm in names.items():
        vals = sorted(t["features"][k] for t in trades if k in t["features"])
        if len(vals) < 2:
            continue
        med = vals[len(vals) // 2]
        lo = [t for t in trades if k in t["features"] and t["features"][k] < med]
        hi = [t for t in trades if k in t["features"] and t["features"][k] >= med]
        if not lo or not hi:
            continue
        out["features"][k] = {"name": nm, "median": med, "low": st(lo), "high": st(hi)}
        if len(lo) >= 6 and len(hi) >= 6:
            dr = out["features"][k]["high"]["avg_r"] - out["features"][k]["low"]["avg_r"]
            if abs(dr) >= 0.3:
                better = "higher" if dr > 0 else "lower"
                out["lessons"].append(
                    f"Trades with {better} {nm} (split at {med:g}) did better: "
                    f"{out['features'][k]['high' if dr > 0 else 'low']['avg_r']:+.2f}R vs "
                    f"{out['features'][k]['low' if dr > 0 else 'high']['avg_r']:+.2f}R per trade.")
    for g in GROUP_TAGS:
        d = out["tags"].get(g)
        if d and d["n"] >= 4:
            out["lessons"].append(f"{TAG_TEXT[g].capitalize()}: {d['n']} trades, win rate {d['win_rate']:.0f}%, "
                                  f"{d['avg_r']:+.2f}R avg, {d['pnl']:+.2f} USD.")
    for tag, d in sorted(out["tags"].items(), key=lambda kv: kv[1]["pnl"]):
        if (d["n"] >= 4 and d["avg_r"] < -0.3 and tag not in GROUP_TAGS
                and tag not in ("immediate_reversal", "good_exit")):
            out["lessons"].append(
                f"'{TAG_TEXT.get(tag, tag)}' trades lose: {d['n']} trades, win rate {d['win_rate']:.0f}%, "
                f"{d['avg_r']:+.2f}R each, {d['pnl']:+.2f} USD total.")
    if len(out["lessons"]) == 0:
        out["lessons"].append(f"{len(trades)} closed trades so far - not enough for reliable patterns (needs ~8+ per group).")
    return out


def neighbours(params):
    out = []
    for k, grid in TUNE_GRID.items():
        if k in params.get("locked", []):
            continue
        cur = params[k]
        idx = min(range(len(grid)), key=lambda j: abs(grid[j] - cur))
        for j in (idx - 1, idx + 1):
            if 0 <= j < len(grid) and grid[j] != cur:
                c = dict(params)
                c[k] = grid[j]
                out.append((k, cur, grid[j], c))
    return out


def learn(settings, simulate=False, seed=7, verbose=True):
    params = load_params()
    say = log if verbose else (lambda m: None)
    syms = [s for s in settings["symbols"] if s not in params.get("disabled_instruments", [])]
    say(f"Learning: loading {settings['learn_days']} days of hourly prices for {len(syms)} markets...")
    data = get_data(settings, settings["learn_days"], simulate, seed, syms)
    if not data:
        raise RuntimeError("no price history could be loaded")
    times = sorted({c["t"] for cs in data.values() for c in cs})
    split = times[int(len(times) * 2 / 3)]
    cur_tr = run_sim(settings, params, data, t_end=split)
    cur_te = run_sim(settings, params, data, t_start=split)
    say(f"Current strategy v{params['version']}: train {cur_tr['ret']:+.2f}% (DD {cur_tr['mdd']:.1f}%, "
        f"{cur_tr['n']} trades) | unseen {cur_te['ret']:+.2f}% (DD {cur_te['mdd']:.1f}%, {cur_te['n']} trades)")
    cands = [(run_sim(settings, c, data, t_end=split), k, old, new, c) for k, old, new, c in neighbours(params)]
    cands.sort(key=lambda x: -x[0]["score"])
    margin = settings["learn_margin"]
    adopted, tested = None, []
    for tr, k, old, new, c in cands[:3]:
        if tr["score"] <= cur_tr["score"] + margin:
            break
        te = run_sim(settings, c, data, t_start=split)
        tested.append((k, old, new, tr, te))
        if te["score"] > cur_te["score"] + margin and te["n"] >= 8 and te["mdd"] <= cur_te["mdd"] + 2.0:
            adopted = (k, old, new, tr, te, c)
            break
    # how each side / class did over the whole 90 days with the current settings
    full = analyse(cur_tr["trades"] + cur_te["trades"])
    groups = "; ".join(f"{g} {full['tags'][g]['n']} trades {full['tags'][g]['pnl']:+.2f} USD"
                       for g in GROUP_TAGS if g in full["tags"])
    journal = analyse(load_trades())
    entry = [f"\n## {now_iso()} - daily learning (strategy v{params['version']}, agent {VERSION})\n",
             f"Data: last {settings['learn_days']} days, {len(data)} markets{' (SIMULATED)' if simulate else ''}; "
             f"tuned on the first 2/3, checked on the last 1/3 (unseen).\n",
             f"- Current: train {cur_tr['ret']:+.2f}% (max DD {cur_tr['mdd']:.1f}%, {cur_tr['n']} trades, "
             f"win {cur_tr['win_rate']:.0f}%) | unseen {cur_te['ret']:+.2f}% (max DD {cur_te['mdd']:.1f}%, "
             f"{cur_te['n']} trades)\n",
             f"- By side and market over all 90 days: {groups or 'no trades'}\n"]
    if adopted:
        k, old, new, tr, te, c = adopted
        c["version"] = params["version"] + 1
        c["updated"] = now_iso()
        c["last_change"] = f"{k}: {old} -> {new}"
        evidence = []
        for tag in PARAM_TAGS.get(k, []):
            d = journal["tags"].get(tag)
            if d:
                evidence.append(f"live journal: {d['n']} '{TAG_TEXT[tag]}' trades, win rate "
                                f"{d['win_rate']:.0f}%, {d['avg_r']:+.2f}R avg")
        entry.append(
            f"- **CHANGED {LABEL.get(k, k)}: {old} -> {new}** (now v{c['version']}). "
            f"Train {cur_tr['ret']:+.2f}% -> {tr['ret']:+.2f}%, unseen {cur_te['ret']:+.2f}% -> "
            f"{te['ret']:+.2f}%, unseen max DD {cur_te['mdd']:.1f}% -> {te['mdd']:.1f}%."
            f"{' Evidence: ' + '; '.join(evidence) + '.' if evidence else ''}\n")
        write_json(PARAMS_FILE, c)
        say(f"Adopted change {k}: {old} -> {new} (strategy v{c['version']})")
    else:
        if tested:
            why = "; ".join(f"{k} {o}->{n} looked better in training ({tr['ret']:+.2f}%) but not on unseen "
                            f"data ({te['ret']:+.2f}%, {te['n']} trades)" for k, o, n, tr, te in tested)
            entry.append(f"- No change: {why}. Rejected as likely overfitting.\n")
        else:
            entry.append("- No change: no small tweak beat the current settings in training by enough.\n")
        say("No change adopted.")
    entry.append("- Lessons from live trades so far: " + " ".join(journal["lessons"]) + "\n")
    append(CHANGELOG_FILE, "".join(entry))
    return {"adopted": adopted is not None, "text": "".join(entry), "journal": journal}


# --------------------------------------------------------------------------- reports
def write_report(state, learn_text=""):
    os.makedirs(REPORTS_DIR, exist_ok=True)
    trades = load_trades()
    params = load_params()
    eq = Agent(SETTINGS, params, state).equity()
    start = state["starting_cash"]
    day_ago = time.time() - 86400
    recent = [t for t in trades if t.get("closed_t", 0) >= day_ago]
    j = analyse(trades)
    lines = [f"# Daily report - {datetime.now(timezone.utc).strftime('%Y-%m-%d')}\n",
             f"Equity **${eq:,.2f}** ({(eq / start - 1) * 100:+.2f}% since {state['created']}), "
             f"free cash ${state['cash']:,.2f}, strategy v{params['version']}, agent {VERSION}.\n",
             f"\n## Last 24h: {len(recent)} closed trades, P&L {sum(t['pnl'] for t in recent):+.2f} USD\n"]
    for t in recent:
        lines.append(f"- #{t['id']} {t.get('side', 'long')} {t.get('name', t['symbol'])} {t['pnl']:+.2f} "
                     f"({t['r']:+.2f}R, {t['exit_reason']}): {t['verdict']}\n")
    lines.append("\n## Open positions\n")
    for sym, p in state["positions"].items():
        px = state["last_prices"].get(sym, p["entry"])
        lines.append(f"- #{p['id']} {p['side']} {name(sym)} entry {fmt_px(p['entry'])}, now {fmt_px(px)}, "
                     f"stop {fmt_px(p['stop'])}, target {fmt_px(p['tp'])}, "
                     f"unrealized {p['dir'] * (px - p['entry']) * p['qty'] - p['entry_fee']:+.2f}\n")
    if not state["positions"]:
        lines.append("- none\n")
    if trades:
        lines.append(f"\n## All closed trades: {j['n']}, win rate {j['win_rate']:.0f}%, "
                     f"{j['avg_r']:+.2f}R avg, P&L {j['pnl']:+.2f} USD\n\n"
                     "| group / cause / condition | trades | win rate | avg R | P&L |\n|---|---|---|---|---|\n")
        for tag, d in sorted(j["tags"].items(), key=lambda kv: (kv[0] not in GROUP_TAGS, -kv[1]["n"])):
            lines.append(f"| {TAG_TEXT.get(tag, tag)} | {d['n']} | {d['win_rate']:.0f}% | "
                         f"{d['avg_r']:+.2f} | {d['pnl']:+.2f} |\n")
    lines.append("\n## Lessons\n" + "".join(f"- {l}\n" for l in j["lessons"]))
    if state["skipped"]:
        lines.append("\n## Signals skipped by filters (cumulative)\n" +
                     "".join(f"- {k}: {v}\n" for k, v in state["skipped"].items()))
    if learn_text:
        lines.append("\n## Today's learning step\n" + learn_text)
    path = os.path.join(REPORTS_DIR, datetime.now(timezone.utc).strftime("%Y-%m-%d") + ".md")
    with open(path, "w") as f:
        f.write("".join(lines))
    return path


# --------------------------------------------------------------------------- live loop
def ensure_files():
    if not os.path.exists(PARAMS_FILE):
        p = dict(DEFAULT_PARAMS)
        p["updated"] = now_iso()
        write_json(PARAMS_FILE, p)
    if not os.path.exists(JOURNAL_FILE):
        append(JOURNAL_FILE, "# Trade journal\nEvery trade: why it was taken, what happened, why it worked "
                             "or failed, and a follow-up 12h after the exit.\n")
    if not os.path.exists(CHANGELOG_FILE):
        append(CHANGELOG_FILE, "# Strategy changelog\nEvery learning step and every change to the "
                               "strategy, with the evidence for it.\n")
    os.makedirs(REPORTS_DIR, exist_ok=True)


def cycle(agent):
    gran = SETTINGS["granularity"]
    s = agent.s
    progressed = False
    for sym in SETTINGS["symbols"]:
        now = time.time()
        if now < s["next_check"].get(sym, 0):
            continue
        last = s["last_candle"].get(sym)
        try:
            closed = fetch_recent(sym, gran)
        except Exception as e:
            log(f"! could not fetch {name(sym)}: {e} (will retry)")
            s["next_check"][sym] = now + 300
            continue
        if not closed:
            s["next_check"][sym] = now + 600
            continue
        s["last_prices"][sym] = closed[-1]["close"]
        new_idx = [i for i, c in enumerate(closed) if last is None or c["t"] > last]
        if last is None:
            new_idx = new_idx[-1:]
        if new_idx:
            S = compute(closed, agent.p)
            for i in new_idx:
                agent.step(sym, closed, i, S, s["last_prices"])
                s["last_candle"][sym] = closed[i]["t"]
            progressed = True
            # the next candle closes at last + 2*gran; check shortly after that
            s["next_check"][sym] = s["last_candle"][sym] + 2 * gran + 30
        else:
            # market closed (weekend / break) or data delayed: look again in 10 minutes
            s["next_check"][sym] = now + 600
    s["src_pref"] = dict(SRC_PREF)
    s["yahoo"] = {"block_until": YAHOO["block_until"], "backoff": YAHOO["backoff"]}
    if progressed:
        eq = agent.equity()
        s["equity_history"] = (s["equity_history"] + [{"time": now_iso(), "equity": round(eq, 2)}])[-5000:]
        held = ", ".join(f"{name(x)} {p['side']}" for x, p in s["positions"].items()) or "-"
        halt = "  [HALTED: drawdown limit]" if agent.halted(s["last_prices"]) else ""
        log(f"equity ${eq:,.2f}  free cash ${s['cash']:,.2f}  v{agent.p['version']}  |  open: {held}{halt}")
    write_json(STATE_FILE, s)


def cmd_run(args):
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(line_buffering=True)
    ensure_files()
    state = load_state()
    if state.get("agent_version") != VERSION:
        log(f"Agent upgraded {state.get('agent_version')} -> {VERSION}: re-learning now with the new capabilities.")
        state["agent_version"] = VERSION
        state["last_learn"] = 0
    SRC_PREF.update(state.get("src_pref", {}))
    YAHOO.update(state.get("yahoo", {}))
    params = load_params()
    agent = Agent(SETTINGS, params, state, TRADES_FILE, JOURNAL_FILE, verbose=True)
    p_mtime = os.path.getmtime(PARAMS_FILE)
    code_mtime = os.path.getmtime(os.path.abspath(__file__))
    log(f"Paper trading agent v{VERSION} started in {HERE} - strategy v{params['version']}, "
        f"{len(SETTINGS['symbols'])} markets, longs {'on' if params.get('allow_longs', True) else 'off'}, "
        f"shorts {'on' if params.get('allow_shorts', True) else 'off'}, "
        f"Yahoo client {'curl_cffi' if _cffi else 'urllib'}, equity ${agent.equity():,.2f}. Paper money only.")
    while True:
        try:
            if os.path.getmtime(os.path.abspath(__file__)) != code_mtime:
                write_json(STATE_FILE, state)
                log("Agent code was updated - restarting to load the new version.")
                sys.exit(0)        # the background service starts it again within a minute
            m = os.path.getmtime(PARAMS_FILE)
            if m != p_mtime:
                agent.p, p_mtime = load_params(), m
                log(f"params.json changed - now using strategy v{agent.p['version']}")
            cycle(agent)
            if time.time() - state["last_learn"] >= SETTINGS["learn_every_hours"] * 3600:
                # if learning fails (e.g. no internet) retry in about an hour, not a day
                state["last_learn"] = time.time() - (SETTINGS["learn_every_hours"] - 1) * 3600
                write_json(STATE_FILE, state)
                res = learn(SETTINGS)
                state["last_learn"] = time.time()
                agent.p, p_mtime = load_params(), os.path.getmtime(PARAMS_FILE)
                log(f"Daily report written: {write_report(state, res['text'])}")
        except (KeyboardInterrupt, SystemExit):
            raise
        except Exception:
            log("! error in cycle (will continue):\n" + traceback.format_exc())
        if args.once:
            break
        time.sleep(SETTINGS["poll_seconds"])


def cmd_status(args):
    if not os.path.exists(STATE_FILE):
        print("No portfolio yet. Start with: python3 paper_agent.py run")
        return
    state, params = load_state(), load_params()
    eq = Agent(SETTINGS, params, state).equity()
    start = state["starting_cash"]
    print(f"\nEquity ${eq:,.2f} ({(eq / start - 1) * 100:+.2f}%)  free cash ${state['cash']:,.2f}  "
          f"strategy v{params['version']}  agent {state.get('agent_version')}  since {state['created']}")
    for sym, p in state["positions"].items():
        px = state["last_prices"].get(sym, p["entry"])
        print(f"  OPEN #{p['id']} {p['side']:5} {name(sym):9} entry {fmt_px(p['entry'])} now {fmt_px(px)} "
              f"stop {fmt_px(p['stop'])} target {fmt_px(p['tp'])} "
              f"uP&L {p['dir'] * (px - p['entry']) * p['qty'] - p['entry_fee']:+.2f}")
    j = analyse(load_trades())
    if j["n"]:
        print(f"  Closed {j['n']}, win rate {j['win_rate']:.0f}%, {j['avg_r']:+.2f}R avg, P&L {j['pnl']:+.2f}")
    print("  Lessons: " + " ".join(j["lessons"]) + "\n")


def cmd_backtest(args):
    data = get_data(SETTINGS, args.days, args.simulate, args.seed)
    params = load_params()
    jp = P("backtest_journal.md") if args.journal else None
    if jp and os.path.exists(jp):
        os.remove(jp)
    res = run_sim(SETTINGS, params, data, journal_path=jp)
    print(f"{'SIMULATED' if args.simulate else 'Real'} data, {args.days} days, {len(data)} markets, strategy v{params['version']}")
    print(f"  Final ${res['final']:,.2f} ({res['ret']:+.2f}%)   max DD {res['mdd']:.1f}%")
    print(f"  {res['n']} trades, win rate {res['win_rate']:.0f}%, {res['avg_r']:+.2f}R avg, still open: "
          f"{', '.join(name(s) for s in res['open']) or 'none'}")
    j = analyse(res["trades"])
    for tag, d in sorted(j["tags"].items(), key=lambda kv: (kv[0] not in GROUP_TAGS, -kv[1]["n"])):
        print(f"    {TAG_TEXT.get(tag, tag):46} n={d['n']:3}  win {d['win_rate']:3.0f}%  {d['avg_r']:+.2f}R  {d['pnl']:+8.2f} USD")
    print("  Lessons: " + " ".join(j["lessons"]))
    if jp:
        print(f"  Journal written to {jp}")


def cmd_learn(args):
    ensure_files()
    print(learn(SETTINGS, simulate=args.simulate, seed=args.seed)["text"])


def cmd_check(args):
    ok = True
    for sym in SETTINGS["symbols"]:
        try:
            cs, src = fetch_any(sym, SETTINGS["granularity"], 30, True)
            print(f"  OK   {name(sym):10} via {src:22} last hourly close {fmt_px(cs[-1]['close'])} ({ts_iso(cs[-1]['t'])})")
        except Exception as e:
            ok = False
            print(f"  FAIL {name(sym):10} {e}")
    print("All markets reachable." if ok else "Some markets could not be reached (the agent retries automatically).")
    if not ok:
        sys.exit(1)


def cmd_reset(args):
    for f in (STATE_FILE, TRADES_FILE, JOURNAL_FILE):
        if os.path.exists(f):
            os.replace(f, f + ".old")
    ensure_files()
    write_json(STATE_FILE, new_state(SETTINGS))
    print("Portfolio reset to $1,000 (previous files kept as *.old; params and changelog unchanged).")


def main():
    ap = argparse.ArgumentParser(description="Self-improving paper trading agent")
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run")
    r.add_argument("--once", action="store_true")
    sub.add_parser("status")
    b = sub.add_parser("backtest")
    b.add_argument("--days", type=int, default=60)
    b.add_argument("--simulate", action="store_true")
    b.add_argument("--journal", action="store_true")
    b.add_argument("--seed", type=int, default=7)
    l = sub.add_parser("learn")
    l.add_argument("--simulate", action="store_true")
    l.add_argument("--seed", type=int, default=7)
    sub.add_parser("check")
    sub.add_parser("reset")
    a = ap.parse_args()
    {"run": cmd_run, "status": cmd_status, "backtest": cmd_backtest, "learn": cmd_learn,
     "check": cmd_check, "reset": cmd_reset}[a.cmd](a)


if __name__ == "__main__":
    main()

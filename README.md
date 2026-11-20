# Paper Trading Agent

A self-reviewing trading bot that trades **$1,000 of paper money** — long and short — across
crypto, forex and commodities on live hourly prices. It runs in the cloud on **GitHub Actions**
every hour, writes down why it takes every trade, studies every win and loss, and tunes its own
strategy once a day.

> **Paper money only.** No real orders are ever placed, and no exchange account or API key is
> needed. This is for learning and experimentation — not financial advice.

---

## At a glance

| | |
|---|---|
| **Starting balance** | $1,000 (paper) |
| **Markets** | 11: 3 crypto, 4 forex, 4 commodities |
| **Directions** | Long and short |
| **Timeframe** | Hourly candles |
| **Runs** | Every hour at :07 on GitHub Actions (free) |
| **Learns** | Once a day, on 90 days of real prices |
| **Latest status** | [`status.txt`](status.txt) — updated every hour |

## Markets

| Market | Asset class | Price source | Backup source | Leverage | Trading costs per fill |
|---|---|---|---|---|---|
| Bitcoin | Crypto | Coinbase | — | 1× | 0.10% fee + 0.05% slippage |
| Ethereum | Crypto | Coinbase | — | 1× | 0.10% fee + 0.05% slippage |
| Solana | Crypto | Coinbase | — | 1× | 0.10% fee + 0.05% slippage |
| EUR/USD | Forex | Yahoo Finance | Kraken | 10× | 0.01% spread |
| GBP/USD | Forex | Yahoo Finance | Kraken | 10× | 0.012% spread |
| AUD/USD | Forex | Yahoo Finance | Kraken | 10× | 0.015% spread |
| NZD/USD | Forex | Yahoo Finance | — | 10× | 0.02% spread |
| Gold | Commodity | Yahoo Finance (futures) | PAXG on Coinbase | 5× | 0.02% fee + 0.02% slippage |
| Silver | Commodity | Yahoo Finance (futures) | — | 5× | 0.02% fee + 0.04% slippage |
| Crude oil (WTI) | Commodity | Yahoo Finance (futures) | — | 5× | 0.02% fee + 0.04% slippage |
| Copper | Commodity | Yahoo Finance (futures) | — | 5× | 0.02% fee + 0.04% slippage |

All price data is free and needs no key. Shorting crypto is charged a borrowing fee of about 10%
a year. PAXG is a gold-backed token that tracks the gold price.

**If a price source fails**, the bot switches to the backup and keeps using whichever source last
worked, so a market's price history doesn't jump between sources. Yahoo Finance often blocks
automated requests; when it does, the bot pauses Yahoo for 15 minutes, then waits longer each
time it's still blocked (up to 6 hours). Markets with no backup sit out until Yahoo responds.
On GitHub Actions the bot installs [`curl_cffi`](https://github.com/lexiforest/curl_cffi), which
connects to Yahoo the way Chrome does and is often let through.

## How it trades

A trend-following strategy on hourly candles:

| | Long | Short |
|---|---|---|
| **Signal** | Fast EMA (12) crosses **above** slow EMA (26) within the last 3 hours | Fast EMA crosses **below** slow EMA within the last 3 hours |
| **Trend filter** | Price **above** the trend EMA (100) | Price **below** the trend EMA (100) |
| **Momentum filter** | RSI between 45 and 70 | RSI between 30 and 55 |
| **Stop-loss** | 2 ATR below entry, trailing 2.5 ATR behind price | 2 ATR above entry, trailing 2.5 ATR behind price |
| **Take-profit** | 4 ATR above entry | 4 ATR below entry |
| **Early exit** | EMAs cross back | EMAs cross back |

*ATR = average true range, a measure of how much the price typically moves in an hour.*

**Risk controls**

- Each trade risks **0.75% of the account** (distance to the stop-loss × position size).
- No single position uses more than **33% of the account** as margin.
- At most **5 open positions** at once.
- If the account falls **20% below $1,000**, the bot stops opening new trades.

The learning loop can also switch on optional filters: skip choppy markets, skip late entries
that are already far from the slow EMA, and skip entries on weak volume.

## How it learns

### 1. A written reason before every trade

```
## #12 OPEN SHORT Gold - 2026-11-21 09:00 UTC
Why: Gold: fast EMA crossed BELOW the slow EMA 1h ago, price below the trend EMA.
RSI 41, trend efficiency 0.38 (moderate trend), price 1.2 ATR below the slow EMA,
75% of commodity in downtrends, hourly volatility 0.31%.
Plan: stop 2,618.40 (+2.0 ATR), target 2,580.10 (-4.0 ATR), trailing 2.5 ATR.
Risking about $7.48 (0.7% of equity).
```

### 2. A post-mortem after every trade

When a trade closes, the bot records its best and worst point, why it won or lost, and which
entry conditions likely contributed. **Twelve hours after the exit** it checks again: was the
stop too tight, did it exit too early, or was getting out the right call?

Each trade is tagged so patterns can be counted:

| Tag | Meaning |
|---|---|
| `clean_win` | Hit the profit target |
| `immediate_reversal` | Turned against the trade straight after entry |
| `gave_back` | Was well in profit, then gave it back |
| `shaken_out` | Stopped out, then price went on to where the trade expected |
| `exited_early` | Kept moving the trade's way after the exit |
| `good_exit` | Price moved further against the position after the exit |
| `choppy` / `extended` / `overbought` / `oversold` / `weak_volume` / `against_market` | The conditions at entry |
| `long` / `short` / `crypto` / `forex` / `commodity` | Side and asset class |

Entry conditions are tagged on **every** trade, wins included, so their win rates can be
compared fairly.

### 3. Daily self-tuning, with guards against fooling itself

Once a day the bot downloads 90 days of real prices and re-tests small changes to its settings:
a slightly wider stop, a stricter choppiness filter, and so on. A change is adopted only if:

1. it does better on the **first 60 days** (the training data), **and**
2. it also does better on the **most recent 30 days**, which it wasn't tuned on, **and**
3. it made at least 8 trades in those 30 days, and its worst loss from a peak isn't more than
   2 percentage points worse.

At most **one change a day**, each a single small step. Every learning step — including the
changes it rejected and why — is recorded in [`strategy_changelog.md`](strategy_changelog.md).

### 4. A daily review by Claude

Each day Claude reads the journal, trades, reports and changelog, writes its analysis in
[`review_notes.md`](review_notes.md), and makes at most one evidence-backed change.

## Files

| File | What it is |
|---|---|
| [`status.txt`](status.txt) | Latest equity, open positions and lessons — updated every hour |
| [`journal.md`](journal.md) | Every trade: why it was taken, what happened, why it worked or failed, the 12-hour follow-up |
| [`trades.jsonl`](trades.jsonl) | The same, as data (one JSON record per closed trade) |
| [`reports/`](reports/) | A daily report: profit and loss, results by cause, side and market, lessons, and the learning step |
| [`strategy_changelog.md`](strategy_changelog.md) | Every self-tuning step and strategy change, with the evidence |
| [`review_notes.md`](review_notes.md) | Claude's daily reviews |
| [`params.json`](params.json) | The current strategy settings |
| `state.json` | The bot's memory: cash, open positions, last candles seen |
| [`logs/agent.log`](logs/agent.log) | The activity log (last 3,000 lines) |
| [`paper_agent.py`](paper_agent.py) | The bot — one file, Python standard library only |
| [`.github/workflows/trade.yml`](.github/workflows/trade.yml) | The hourly schedule |

## Running it in the cloud

The workflow in [`.github/workflows/trade.yml`](.github/workflows/trade.yml) runs every hour at
7 minutes past, after the hourly candle closes. Each run:

1. checks out the repository (which holds the bot's memory),
2. runs one trading cycle — and the daily learning step when it's due,
3. commits the updated state, trades, journal and reports back to the repository.

GitHub can delay scheduled runs at busy times; the bot catches up on every candle it missed.

**Controls** — on the repository's **Actions** tab, under **paper-trading-agent**:

- **Run workflow** runs a cycle now.
- **Disable workflow** pauses the bot; **Enable workflow** resumes it.

**Cost** — free. A private repository uses roughly half of GitHub's 2,000 free Actions minutes a
month; a public one has no limit.

## Changing the strategy

Edit [`params.json`](params.json) on GitHub; the next run picks it up.

| Setting | What it does |
|---|---|
| `allow_longs`, `allow_shorts` | Switch either side on or off |
| `disabled_instruments` | Markets to skip, e.g. `["CL=F", "SI=F"]` |
| `risk_per_trade` | Share of the account risked per trade (`0.0075` = 0.75%) |
| `stop_atr`, `take_profit_atr`, `trail_atr` | Exit distances, in ATR |
| `rsi_min`, `rsi_max` | Momentum window, measured in the trade's direction |
| `min_er` | Choppiness filter, 0–1 (`0` = off) |
| `max_ext_atr` | Late-entry filter (`99` = off) |
| `min_vol_ratio` | Volume filter (`0` = off) |
| `locked` | Settings the daily self-tuning must not touch, e.g. `["stop_atr"]` |

## Running it on your own computer

Needs Python 3.8 or newer and nothing else:

```bash
python3 paper_agent.py check              # test every price source
python3 paper_agent.py run                # trade continuously (Ctrl+C to stop; it resumes where it left off)
python3 paper_agent.py run --once         # one cycle, then exit
python3 paper_agent.py status             # account, open positions and lessons
python3 paper_agent.py learn              # run the daily learning step now
python3 paper_agent.py backtest --days 60 # test the current settings on real past prices
python3 paper_agent.py backtest --simulate --journal   # offline test on made-up prices
python3 paper_agent.py reset              # back to $1,000 (keeps settings and changelog)
```

## Limitations

- **Overnight costs are ignored.** Real forex and futures positions pay or earn a small amount
  to be held overnight.
- **Futures roll-overs.** Gold, silver, oil and copper prices come from front-month futures,
  which jump slightly when the contract rolls each month; that can occasionally trigger a stop
  that wouldn't happen in real trading.
- **Weekends.** Forex and commodity markets close at weekends, so those positions sit until Monday.
- **Fills are simplified.** Orders fill at the candle's close plus slippage; stops fill at the stop
  price, or at the open if the price gaps past it.
- **Free price data can be blocked or delayed**, as Yahoo Finance often is.
- **Past results don't predict future ones.** The self-tuning is designed to avoid fitting noise,
  but no amount of testing guarantees a strategy will work.

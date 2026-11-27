# Strategy changelog
Every learning step and every change to the strategy, with the evidence for it.

## 2026-11-19 15:01 UTC - daily learning (strategy v1)
Data: last 90 days; tuned on the first 2/3, checked on the last 1/3 (unseen).
- Current: train -4.82% (max DD 7.4%, 59 trades, win 24%) | unseen +0.68% (max DD 3.7%, 11 trades)
- No change: min_vol_ratio 0.0->0.8 looked better in training (-2.10%) but not on unseen data (+0.65%, 11 trades); rsi_max 70->65 looked better in training (-3.81%) but not on unseen data (+0.65%, 11 trades); trail_atr 2.5->3.0 looked better in training (-4.53%) but not on unseen data (+0.20%, 11 trades). Rejected as likely overfitting.
- Lessons from live trades so far: 

## 2026-11-20 05:18 UTC - manual change by Claude (strategy v2)
- **Added short selling and 8 new markets** (forex: EUR/USD, GBP/USD, AUD/USD, NZD/USD; commodities: gold, silver, WTI crude, copper) in agent v2.1, at the user's request.
- **CHANGED risk per trade: 0.01 -> 0.0075**, and max open positions capped at 5. Reason: with 11 markets and both sides, the agent trades about twice as often and holds more positions at once; in a 90-day simulation at 1% risk, drawdowns reached 15-27%, too close to the 20% safety halt.

## 2026-11-20 06:03 UTC - daily learning (strategy v2, agent 2.1)
Data: last 90 days, 3 markets; tuned on the first 2/3, checked on the last 1/3 (unseen).
- Current: train -9.72% (max DD 13.3%, 113 trades, win 27%) | unseen +2.36% (max DD 4.9%, 37 trades)
- By side and market over all 90 days: long 63 trades -70.08 USD; short 87 trades -13.83 USD; crypto 150 trades -83.92 USD
- No change: min_vol_ratio 0.0->0.8 looked better in training (-4.56%) but not on unseen data (-0.94%, 31 trades); cross_lookback 3->1 looked better in training (-5.95%) but not on unseen data (+1.89%, 30 trades); min_er 0.0->0.1 looked better in training (-7.32%) but not on unseen data (+1.28%, 26 trades). Rejected as likely overfitting.
- Lessons from live trades so far: No closed trades yet - nothing to learn from live trading so far.

## 2026-11-20 06:10 UTC - daily learning (strategy v2, agent 2.2)
Data: last 90 days, 7 markets; tuned on the first 2/3, checked on the last 1/3 (unseen).
- Current: train -12.39% (max DD 16.1%, 147 trades, win 28%) | unseen +4.56% (max DD 4.6%, 67 trades)
- By side and market over all 90 days: long 87 trades -120.67 USD; short 127 trades +32.00 USD; crypto 147 trades -61.72 USD; forex 21 trades -24.88 USD; commodity 46 trades -2.06 USD
- No change: min_er 0.0->0.1 looked better in training (-7.37%) but not on unseen data (-0.39%, 48 trades); min_vol_ratio 0.0->0.8 looked better in training (-9.59%) but not on unseen data (+3.44%, 54 trades); cross_lookback 3->1 looked better in training (-9.73%) but not on unseen data (+2.46%, 56 trades). Rejected as likely overfitting.
- Lessons from live trades so far: No closed trades yet - nothing to learn from live trading so far.

## 2026-11-20 06:42 UTC - moved to the cloud
The agent now runs hourly on GitHub Actions instead of the Mac. Account, settings and history carried over unchanged.

## 2026-11-21 12:33 UTC - daily learning (strategy v2, agent 2.2)
Data: last 90 days, 11 markets; tuned on the first 2/3, checked on the last 1/3 (unseen).
- Current: train -13.10% (max DD 22.6%, 257 trades, win 32%) | unseen +7.24% (max DD 13.1%, 147 trades)
- By side and market over all 90 days: long 174 trades -82.26 USD; short 230 trades +21.63 USD; crypto 131 trades +3.19 USD; forex 146 trades +84.45 USD; commodity 127 trades -148.27 USD
- **CHANGED minimum volume vs average: 0.0 -> 0.8** (now v3). Train -13.10% -> -0.95%, unseen +7.24% -> +10.20%, unseen max DD 13.1% -> 11.4%.
- Lessons from live trades so far: 1 closed trades so far - not enough for reliable patterns (needs ~8+ per group).

## 2026-11-21 20:04 UTC - daily learning (strategy v3, agent 2.2)
Data: last 90 days, 11 markets; tuned on the first 2/3, checked on the last 1/3 (unseen).
- Current: train -2.22% (max DD 13.5%, 225 trades, win 33%) | unseen +9.38% (max DD 11.4%, 129 trades)
- By side and market over all 90 days: long 155 trades -5.36 USD; short 199 trades +75.85 USD; crypto 110 trades +8.60 USD; forex 148 trades +110.97 USD; commodity 96 trades -49.09 USD
- No change: take_profit_atr 4.0->5.0 looked better in training (+1.21%) but not on unseen data (+8.82%, 130 trades); stop_atr 2.0->2.5 looked better in training (-2.08%) but not on unseen data (+7.94%, 127 trades); min_er 0.0->0.1 looked better in training (-3.68%) but not on unseen data (+5.90%, 104 trades). Rejected as likely overfitting.
- Lessons from live trades so far: 1 closed trades so far - not enough for reliable patterns (needs ~8+ per group).

## 2026-11-22 00:19 UTC - daily learning (strategy v3, agent 2.2)
Data: last 90 days, 11 markets; tuned on the first 2/3, checked on the last 1/3 (unseen).
- Current: train +1.05% (max DD 13.5%, 227 trades, win 34%) | unseen +7.28% (max DD 11.4%, 127 trades)
- By side and market over all 90 days: long 155 trades -1.86 USD; short 199 trades +80.68 USD; crypto 110 trades +9.38 USD; forex 148 trades +110.98 USD; commodity 96 trades -41.55 USD
- No change: take_profit_atr 4.0->5.0 looked better in training (+1.95%) but not on unseen data (+6.17%, 128 trades); stop_atr 2.0->2.5 looked better in training (+0.64%) but not on unseen data (+5.89%, 125 trades); min_er 0.0->0.1 looked better in training (-0.56%) but not on unseen data (+3.70%, 102 trades). Rejected as likely overfitting.
- Lessons from live trades so far: 1 closed trades so far - not enough for reliable patterns (needs ~8+ per group).

## 2026-11-22 07:57 UTC - daily learning (strategy v3, agent 2.2)
Data: last 90 days, 11 markets; tuned on the first 2/3, checked on the last 1/3 (unseen).
- Current: train -2.02% (max DD 13.5%, 227 trades, win 33%) | unseen +7.98% (max DD 11.4%, 126 trades)
- By side and market over all 90 days: long 155 trades -3.47 USD; short 198 trades +54.36 USD; crypto 110 trades +9.36 USD; forex 148 trades +110.84 USD; commodity 95 trades -69.31 USD
- No change: min_er 0.0->0.1 looked better in training (-2.10%) but not on unseen data (+4.39%, 101 trades); take_profit_atr 4.0->5.0 looked better in training (-0.47%) but not on unseen data (+6.87%, 127 trades); stop_atr 2.0->2.5 looked better in training (-2.09%) but not on unseen data (+6.61%, 124 trades). Rejected as likely overfitting.
- Lessons from live trades so far: 1 closed trades so far - not enough for reliable patterns (needs ~8+ per group).

## 2026-11-22 16:13 UTC - daily learning (strategy v3, agent 2.2)
Data: last 90 days, 11 markets; tuned on the first 2/3, checked on the last 1/3 (unseen).
- Current: train +1.01% (max DD 13.5%, 227 trades, win 34%) | unseen +6.30% (max DD 11.4%, 125 trades)
- By side and market over all 90 days: long 153 trades -12.83 USD; short 199 trades +89.43 USD; crypto 110 trades +16.79 USD; forex 146 trades +101.14 USD; commodity 96 trades -41.33 USD
- No change: min_er 0.0->0.1 looked better in training (+0.71%) but not on unseen data (+2.22%, 101 trades); take_profit_atr 4.0->5.0 looked better in training (+1.59%) but not on unseen data (+4.81%, 126 trades); stop_atr 2.0->2.5 looked better in training (+0.50%) but not on unseen data (+5.02%, 123 trades). Rejected as likely overfitting.
- Lessons from live trades so far: 3 closed trades so far - not enough for reliable patterns (needs ~8+ per group).

## 2026-11-22 22:26 UTC - daily learning (strategy v3, agent 2.2)
Data: last 90 days, 11 markets; tuned on the first 2/3, checked on the last 1/3 (unseen).
- Current: train +0.83% (max DD 13.5%, 225 trades, win 35%) | unseen +6.31% (max DD 11.4%, 125 trades)
- By side and market over all 90 days: long 152 trades -9.39 USD; short 198 trades +80.18 USD; crypto 108 trades +25.48 USD; forex 146 trades +101.07 USD; commodity 96 trades -55.76 USD
- No change: take_profit_atr 4.0->5.0 looked better in training (+2.90%) but not on unseen data (+4.82%, 126 trades); min_er 0.0->0.1 looked better in training (+0.15%) but not on unseen data (+2.25%, 101 trades); stop_atr 2.0->2.5 looked better in training (+0.34%) but not on unseen data (+5.03%, 123 trades). Rejected as likely overfitting.
- Lessons from live trades so far: 3 closed trades so far - not enough for reliable patterns (needs ~8+ per group).

## 2026-11-23 03:41 UTC - daily learning (strategy v3, agent 2.2)
Data: last 90 days, 11 markets; tuned on the first 2/3, checked on the last 1/3 (unseen).
- Current: train +4.00% (max DD 13.5%, 221 trades, win 35%) | unseen +5.13% (max DD 11.3%, 125 trades)
- By side and market over all 90 days: long 149 trades -3.48 USD; short 197 trades +92.87 USD; crypto 106 trades +17.99 USD; forex 145 trades +117.28 USD; commodity 95 trades -45.87 USD
- No change: min_er 0.0->0.1 looked better in training (+4.35%) but not on unseen data (+1.52%, 100 trades); stop_atr 2.0->2.5 looked better in training (+3.97%) but not on unseen data (+4.03%, 123 trades); take_profit_atr 4.0->5.0 looked better in training (+4.52%) but not on unseen data (+3.65%, 126 trades). Rejected as likely overfitting.
- Lessons from live trades so far: All short trades: 4 trades, win rate 25%, -0.21R avg, -4.89 USD.

## 2026-11-23 07:12 UTC - daily learning (strategy v3, agent 2.2)
Data: last 90 days, 11 markets; tuned on the first 2/3, checked on the last 1/3 (unseen).
- Current: train +2.43% (max DD 13.5%, 221 trades, win 35%) | unseen +5.18% (max DD 11.4%, 125 trades)
- By side and market over all 90 days: long 149 trades -4.69 USD; short 197 trades +79.35 USD; crypto 106 trades +17.77 USD; forex 145 trades +117.52 USD; commodity 95 trades -60.63 USD
- No change: min_er 0.0->0.1 looked better in training (+2.83%) but not on unseen data (+1.25%, 100 trades); take_profit_atr 4.0->5.0 looked better in training (+4.34%) but not on unseen data (+3.70%, 126 trades); stop_atr 2.0->2.5 looked better in training (+2.71%) but not on unseen data (+3.88%, 123 trades). Rejected as likely overfitting.
- Lessons from live trades so far: All short trades: 4 trades, win rate 25%, -0.21R avg, -4.89 USD.

## 2026-11-24 08:07 UTC - daily learning (strategy v3, agent 2.2)
Data: last 90 days, 11 markets; tuned on the first 2/3, checked on the last 1/3 (unseen).
- Current: train +0.78% (max DD 13.5%, 217 trades, win 34%) | unseen +10.23% (max DD 9.2%, 124 trades)
- By side and market over all 90 days: long 147 trades -39.32 USD; short 194 trades +138.97 USD; crypto 101 trades +18.87 USD; forex 145 trades +126.58 USD; commodity 95 trades -45.80 USD
- No change: min_er 0.0->0.1 looked better in training (+0.97%) but not on unseen data (+6.22%, 100 trades); stop_atr 2.0->2.5 looked better in training (+1.32%) but not on unseen data (+8.77%, 122 trades); take_profit_atr 4.0->5.0 looked better in training (+1.25%) but not on unseen data (+9.40%, 125 trades). Rejected as likely overfitting.
- Lessons from live trades so far: All short trades: 6 trades, win rate 50%, +0.51R avg, +19.82 USD. All forex trades: 4 trades, win rate 75%, +1.27R avg, +34.21 USD.

## 2026-11-25 08:21 UTC - daily learning (strategy v3, agent 2.2)
Data: last 90 days, 11 markets; tuned on the first 2/3, checked on the last 1/3 (unseen).
- Current: train +0.79% (max DD 13.5%, 218 trades, win 34%) | unseen +11.23% (max DD 9.2%, 129 trades)
- By side and market over all 90 days: long 148 trades -48.63 USD; short 199 trades +138.82 USD; crypto 102 trades +16.79 USD; forex 147 trades +119.43 USD; commodity 98 trades -46.03 USD
- **CHANGED stop-loss distance (ATR): 2.0 -> 2.5** (now v4). Train +0.79% -> +1.24%, unseen +11.23% -> +10.34%, unseen max DD 9.2% -> 6.6%. Evidence: live journal: 1 'stopped out, then price recovered' trades, win rate 0%, -1.02R avg; live journal: 4 'reversed right after entry' trades, win rate 0%, -1.02R avg.
- Lessons from live trades so far: All short trades: 9 trades, win rate 44%, +0.43R avg, +18.17 USD. All forex trades: 6 trades, win rate 50%, +0.56R avg, +27.50 USD. All commodity trades: 4 trades, win rate 25%, -0.05R avg, -9.59 USD.

## 2026-11-26 09:07 UTC - daily learning (strategy v4, agent 2.2)
Data: last 90 days, 11 markets; tuned on the first 2/3, checked on the last 1/3 (unseen).
- Current: train +1.61% (max DD 11.5%, 217 trades, win 34%) | unseen +7.92% (max DD 6.6%, 132 trades)
- By side and market over all 90 days: long 147 trades -84.00 USD; short 202 trades +175.88 USD; crypto 103 trades -14.39 USD; forex 150 trades +133.48 USD; commodity 96 trades -27.20 USD
- **CHANGED maximum directional RSI to enter: 70 -> 65** (now v5). Train +1.61% -> +2.37%, unseen +7.92% -> +8.53%, unseen max DD 6.6% -> 7.2%. Evidence: live journal: 1 'long entered with RSI > 65' trades, win rate 0%, -0.79R avg.
- Lessons from live trades so far: Trades with lower trend efficiency (split at 0.148) did better: +0.29R vs -0.08R per trade. Trades with higher distance beyond the slow EMA (split at 1.66) did better: +0.38R vs -0.22R per trade. All short trades: 14 trades, win rate 50%, +0.32R avg, +18.37 USD. All crypto trades: 4 trades, win rate 50%, -0.43R avg, -11.61 USD. All forex trades: 9 trades, win rate 44%, +0.40R avg, +24.93 USD. All commodity trades: 4 trades, win rate 25%, -0.05R avg, -9.59 USD.

## 2026-11-27 11:13 UTC - daily learning (strategy v5, agent 2.2)
Data: last 90 days, 11 markets; tuned on the first 2/3, checked on the last 1/3 (unseen).
- Current: train -1.91% (max DD 11.8%, 194 trades, win 34%) | unseen +10.84% (max DD 4.6%, 115 trades)
- By side and market over all 90 days: long 129 trades -77.75 USD; short 180 trades +174.14 USD; crypto 92 trades -2.79 USD; forex 135 trades +136.74 USD; commodity 82 trades -37.57 USD
- **CHANGED minimum directional RSI to enter: 45 -> 50** (now v6). Train -1.91% -> -1.68%, unseen +10.84% -> +11.67%, unseen max DD 4.6% -> 4.6%.
- Lessons from live trades so far: Trades with higher distance beyond the slow EMA (split at 1.66) did better: +0.27R vs -0.24R per trade. All long trades: 4 trades, win rate 0%, -0.88R avg, -20.18 USD. All short trades: 15 trades, win rate 47%, +0.26R avg, +14.85 USD. All crypto trades: 4 trades, win rate 50%, -0.43R avg, -11.61 USD. All forex trades: 11 trades, win rate 36%, +0.21R avg, +15.87 USD. All commodity trades: 4 trades, win rate 25%, -0.05R avg, -9.59 USD.

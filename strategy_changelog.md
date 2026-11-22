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

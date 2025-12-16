import pandas as pd

def mean_reversion_backtest(
    df,
    entry_z=2.0,
    exit_z=0.0
):
    trades = []
    position = 0
    entry_spread = None
    entry_time = None

    for i in range(len(df)):
        z = df["zscore"].iloc[i]
        spread = df["spread"].iloc[i]
        ts = df["ts"].iloc[i]

        if position == 0:
            if z > entry_z:
                position = -1
                entry_spread = spread
                entry_time = ts
            elif z < -entry_z:
                position = 1
                entry_spread = spread
                entry_time = ts

        elif position != 0:
            if (position == 1 and z >= exit_z) or (position == -1 and z <= exit_z):
                pnl = position * (entry_spread - spread)
                trades.append({
                    "entry_time": entry_time,
                    "exit_time": ts,
                    "position": position,
                    "entry_spread": entry_spread,
                    "exit_spread": spread,
                    "pnl": pnl
                })
                position = 0
                entry_spread = None
                entry_time = None

    trades_df = pd.DataFrame(trades)

    if trades_df.empty:
        return trades_df, pd.Series(dtype=float)

    trades_df["cum_pnl"] = trades_df["pnl"].cumsum()

    return trades_df, trades_df["cum_pnl"]

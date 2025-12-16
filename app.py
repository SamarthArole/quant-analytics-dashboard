import streamlit as st
import pandas as pd
import plotly.express as px

from analytics.backtest import mean_reversion_backtest
from storage.datastore import MarketDataStore
from ingestion.binance_ws import BinanceWebSocketIngestor
from resampling.sampler import Resampler

from analytics.hedge import ols_hedge_ratio, compute_spread, compute_zscore
from analytics.correlation import rolling_correlation
from analytics.stationarity import adf_test


st.set_page_config(page_title="Quant Analytics Dashboard", layout="wide")


@st.cache_resource
def start_ingestion():
    datastore = MarketDataStore()
    ingestor = BinanceWebSocketIngestor(
        symbols=["btcusdt", "ethusdt"],
        datastore=datastore
    )
    ingestor.start()
    return datastore


datastore = start_ingestion()
resampler = Resampler(datastore)


@st.cache_data(ttl=5)
def run_resampling():
    for sym in ["btcusdt", "ethusdt"]:
        for tf in ["1s", "1m", "5m"]:
            resampler.resample(sym, tf)
    return True


run_resampling()


st.title("Quant Analytics Dashboard")
st.write("Live data ingestion and aggregation running in background.")


st.sidebar.header("Analytics Controls")
timeframe = st.sidebar.selectbox("Timeframe", ["1s", "1m", "5m"], index=2)
window = st.sidebar.slider("Rolling Window", 10, 100, 50)
refresh = st.sidebar.button("Refresh Analytics")


if refresh or "analytics_loaded" not in st.session_state:
    st.session_state["analytics_loaded"] = True

    btc = datastore.con.execute(
        """
        SELECT ts, close
        FROM ohlc
        WHERE symbol='btcusdt' AND timeframe=?
        ORDER BY ts
        """,
        [timeframe]
    ).fetchdf()

    eth = datastore.con.execute(
        """
        SELECT ts, close
        FROM ohlc
        WHERE symbol='ethusdt' AND timeframe=?
        ORDER BY ts
        """,
        [timeframe]
    ).fetchdf()

    if not btc.empty and not eth.empty:
        df = btc.merge(eth, on="ts", suffixes=("_btc", "_eth"))

        hedge = ols_hedge_ratio(df["close_btc"], df["close_eth"])
        df["spread"] = compute_spread(df["close_btc"], df["close_eth"], hedge)
        df["zscore"] = compute_zscore(df["spread"], window)
        df["corr"] = rolling_correlation(df["close_btc"], df["close_eth"], window)

        st.session_state["df"] = df
        st.session_state["hedge"] = hedge


if "df" not in st.session_state:
    st.warning("Waiting for sufficient data to compute analytics.")
    st.stop()


df = st.session_state["df"]
hedge = st.session_state["hedge"]

st.subheader("Stationarity Test (ADF)")

if st.button("Run ADF Test on Spread"):
    res = adf_test(df["spread"])
    c1, c2 = st.columns(2)

    with c1:
        st.metric("ADF Statistic", f"{res['adf_stat']:.4f}")
        st.metric("p-value", f"{res['p_value']:.4f}")

    with c2:
        st.write(f"Lags used: {res['lags']}")
        st.write(f"Observations: {res['n_obs']}")

    if res["p_value"] < 0.05:
        st.success("Likely stationary (mean-reverting)")
    else:
        st.warning("Not stationary at 5% significance")


st.subheader("Quick Data Checks")

if st.button("Show Latest BTC Ticks"):
    ticks = datastore.get_ticks("btcusdt", 20)
    st.dataframe(ticks)

if st.button("Show Latest 1m BTC OHLC"):
    bars = datastore.con.execute(
        """
        SELECT *
        FROM ohlc
        WHERE symbol='btcusdt' AND timeframe='1m'
        ORDER BY ts DESC
        LIMIT 5
        """
    ).fetchdf()
    st.dataframe(bars)

st.subheader("Mean-Reversion Mini Backtest")

entry_z = st.slider("Entry Z-Score", 1.5, 3.0, 2.0, step=0.1)
exit_z = 0.0

if st.button("Run Backtest"):
    trades, equity = mean_reversion_backtest(
        df,
        entry_z=entry_z,
        exit_z=exit_z
    )

    if trades.empty:
        st.warning("No trades generated for current parameters.")
    else:
        st.metric("Total Trades", len(trades))
        st.metric("Total PnL (Spread Units)", round(trades["pnl"].sum(), 4))
        st.metric("Win Rate", f"{(trades['pnl'] > 0).mean() * 100:.1f}%")

        st.subheader("Equity Curve")
        st.line_chart(equity)

        st.subheader("Trade Log")
        st.dataframe(trades)


st.subheader("Analytics Overview")

col1, col2 = st.columns(2)

with col1:
    st.markdown("### Prices")
    st.plotly_chart(
        px.line(df, x="ts", y=["close_btc", "close_eth"]),
        use_container_width=True
    )

with col2:
    st.markdown("### Spread & Z-Score")
    st.plotly_chart(
        px.line(df, x="ts", y=["spread", "zscore"]),
        use_container_width=True
    )

col3, col4 = st.columns(2)

with col3:
    st.markdown("### Rolling Correlation")
    st.plotly_chart(
        px.line(df, x="ts", y="corr"),
        use_container_width=True
    )

with col4:
    st.markdown("### (Reserved)")
    st.info("Space reserved for future analytics")

st.subheader("Data Export")

export_analytics = df[[
    "ts",
    "close_btc",
    "close_eth",
    "spread",
    "zscore",
    "corr"
]].copy()

export_ohlc = datastore.con.execute(
    """
    SELECT *
    FROM ohlc
    WHERE timeframe=?
    ORDER BY ts
    """,
    [timeframe]
).fetchdf()


st.download_button(
    label="Download Analytics CSV",
    data=export_analytics.to_csv(index=False),
    file_name=f"analytics_{timeframe}.csv",
    mime="text/csv"
)

st.download_button(
    label="Download OHLC CSV",
    data=export_ohlc.to_csv(index=False),
    file_name=f"ohlc_{timeframe}.csv",
    mime="text/csv"
)

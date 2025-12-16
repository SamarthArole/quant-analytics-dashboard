import streamlit as st
import pandas as pd
import plotly.express as px
import time

from storage.datastore import MarketDataStore
from ingestion.binance_ws import BinanceWebSocketIngestor
from resampling.sampler import Resampler

from analytics.stats import compute_returns, rolling_volatility
from analytics.hedge import ols_hedge_ratio, compute_spread, compute_zscore
from analytics.correlation import rolling_correlation
from analytics.stationarity import adf_test


st.set_page_config(page_title="Quant Dashboard", layout="wide")


@st.cache_resource
def start_ingestion():
    datastore = MarketDataStore()
    ingestor = BinanceWebSocketIngestor(
        symbols=["btcusdt", "ethusdt"],
        datastore=datastore
    )
    ingestor.start()
    return datastore

# st.sidebar.checkbox("Live mode", value=True, key="live")

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
st.write("Data ingestion running in background...")


st.sidebar.header("Analytics Controls")
timeframe = st.sidebar.selectbox("Timeframe", ["1s", "1m", "5m"])
window = st.sidebar.slider("Rolling Window", 10, 100, 30)


if st.button("Show 1m BTC bars"):
    df_bars = datastore.con.execute(
        """
        SELECT *
        FROM ohlc
        WHERE symbol='btcusdt' AND timeframe='1m'
        ORDER BY ts DESC
        LIMIT 5
        """
    ).fetchdf()
    st.dataframe(df_bars)


if st.button("Check latest BTC ticks"):
    df_ticks = datastore.get_ticks("btcusdt", 50)
    st.dataframe(df_ticks)


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


df = btc.merge(eth, on="ts", suffixes=("_btc", "_eth"))


hedge = ols_hedge_ratio(df["close_btc"], df["close_eth"])
df["spread"] = compute_spread(df["close_btc"], df["close_eth"], hedge)
df["zscore"] = compute_zscore(df["spread"], window)
df["corr"] = rolling_correlation(df["close_btc"], df["close_eth"], window)

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

st.subheader("Prices")
st.plotly_chart(
    px.line(df, x="ts", y=["close_btc", "close_eth"]),
    use_container_width=True
)

st.subheader("Spread & Z-Score")
st.plotly_chart(
    px.line(df, x="ts", y=["spread", "zscore"]),
    use_container_width=True
)

st.subheader("Rolling Correlation")
st.plotly_chart(
    px.line(df, x="ts", y="corr"),
    use_container_width=True
)


latest_z = df["zscore"].iloc[-1]
if abs(latest_z) > 2:
    st.error(f"Z-score alert triggered: {latest_z:.2f}")

# if st.session_state.get("live"):
#     time.sleep(1)
#     st.rerun()

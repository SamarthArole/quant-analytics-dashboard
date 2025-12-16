import streamlit as st
import plotly.express as px

from analytics.backtest import mean_reversion_backtest
from storage.datastore import MarketDataStore
from ingestion.binance_ws import BinanceWebSocketIngestor
from resampling.sampler import Resampler
from alerts.rules import zscore_alert


from analytics.hedge import ols_hedge_ratio, compute_spread, compute_zscore
from analytics.correlation import rolling_correlation
from analytics.stationarity import adf_test

from utils.config import (
    DEFAULT_SYMBOLS,
    DEFAULT_TIMEFRAME,
    DEFAULT_ROLLING_WINDOW,
    DEFAULT_Z_ALERT_THRESHOLD,
    DEFAULT_BACKTEST_ENTRY_Z,
    SUPPORTED_TIMEFRAMES
)

st.set_page_config(page_title="Stat Arb Analytical Dashboard", layout="wide")


st.markdown(
    """
    <h2 style='margin-bottom:0;'>Statistical Arbitrage Analytical Dashboard</h2>
    <p style='color:gray; margin-top:4px;'>
    BTC–ETH spread monitoring • Mean-reversion analytics • Research prototype
    </p>
    """,
    unsafe_allow_html=True
)


with st.expander("How to use this dashboard"):
    st.markdown(
        """
        1. Select timeframe and rolling window from the sidebar  
        2. Click **Refresh Analytics** to compute latest signals  
        3. Monitor spread & z-score for extremes  
        4. Validate stationarity using the ADF test  
        5. Use the backtest to assess signal behavior (illustrative)
        """
    )


@st.cache_resource
def start_ingestion():
    datastore = MarketDataStore()
    ingestor = BinanceWebSocketIngestor(
        symbols=DEFAULT_SYMBOLS,
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


st.sidebar.header("Analytics Controls")
timeframes = SUPPORTED_TIMEFRAMES
default_tf_index = timeframes.index(DEFAULT_TIMEFRAME)
timeframe = st.sidebar.selectbox("Timeframe", timeframes, index=default_tf_index)
window = st.sidebar.slider("Rolling Window", 10, 100, DEFAULT_ROLLING_WINDOW)

refresh = st.sidebar.button("Refresh Analytics", use_container_width=True)


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

st.sidebar.subheader("Alert Settings")
alert_enabled = st.sidebar.checkbox("Enable Z-Score Alerts", value=True)
alert_threshold = st.sidebar.slider(
    "Z-Score Threshold",
    1.0,
    3.0,
    DEFAULT_Z_ALERT_THRESHOLD,
    step=0.1
)



latest_z = df["zscore"].iloc[-1]
if alert_enabled and zscore_alert(latest_z, alert_threshold):
    st.markdown(
        f"""
        <div style="padding:12px; border-radius:6px; background-color:#3b0a0a; color:#ffb3b3;">
        <b>⚠ Mean-Reversion Alert</b><br>
        Z-score {latest_z:.2f} breached user threshold ({alert_threshold:.2f})
        </div>
        """,
        unsafe_allow_html=True
    )




with st.container():
    st.markdown("### 📊 Analytics Overview")

    col1, col2 = st.columns(2)

    with col1:
        st.markdown("**Prices**")
        st.plotly_chart(
            px.line(df, x="ts", y=["close_btc", "close_eth"]),
            use_container_width=True
        )

    with col2:
        st.markdown("**Spread & Z-Score**")
        st.plotly_chart(
            px.line(df, x="ts", y=["spread", "zscore"]),
            use_container_width=True
        )

    col3, col4 = st.columns(2)

    with col3:
        st.markdown("**Rolling Correlation**")
        st.plotly_chart(
            px.line(df, x="ts", y="corr"),
            use_container_width=True
        )

    with col4:
        st.info("Space reserved for future analytics")


with st.container():
    st.markdown("### 📉 Stationarity Test (ADF)")

    if st.button("Run ADF Test", use_container_width=True):
        res = adf_test(df["spread"])

        c1, c2 = st.columns(2)
        with c1:
            st.metric("ADF Statistic", f"{res['adf_stat']:.4f}")
            st.metric("p-value", f"{res['p_value']:.4f}")

        with c2:
            st.write(f"Lags used: {res['lags']}")
            st.write(f"Observations: {res['n_obs']}")

        if res["p_value"] < 0.05:
            st.success("Interpretation: Spread is likely stationary (mean-reverting).")
        else:
            st.warning("Interpretation: No strong evidence of stationarity at 5% level.")


with st.container():
    st.markdown("### 🧪 Strategy Validation (Illustrative Backtest)")
    st.info(
        "This backtest is illustrative and intended for signal validation only. "
        "It does not include transaction costs, execution constraints, or risk management."
    )

    entry_z = st.slider( "Entry Z-Score", 1.5, 3.0, DEFAULT_BACKTEST_ENTRY_Z, step=0.1)
    exit_z = 0.0

    if st.button("Run Backtest", use_container_width=True):
        trades, equity = mean_reversion_backtest(df, entry_z, exit_z)

        if trades.empty:
            st.warning("No trades generated for current parameters.")
        else:
            st.metric("Total Trades", len(trades))
            st.metric("Total PnL (Spread Units)", round(trades["pnl"].sum(), 4))
            st.metric("Win Rate", f"{(trades['pnl'] > 0).mean() * 100:.1f}%")

            st.markdown("**Equity Curve**")
            st.line_chart(equity)

            st.markdown("**Trade Log**")
            st.dataframe(trades)


with st.container():
    st.markdown("### 📁 Data Export")

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
        mime="text/csv",
        use_container_width=True
    )

    st.download_button(
        label="Download OHLC CSV",
        data=export_ohlc.to_csv(index=False),
        file_name=f"ohlc_{timeframe}.csv",
        mime="text/csv",
        use_container_width=True
    )

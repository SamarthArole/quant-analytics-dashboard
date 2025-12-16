Quant Analytics Dashboard
Overview

This project is a real-time quantitative analytics dashboard designed as a research-oriented prototype for market microstructure and statistical arbitrage analysis. The system ingests live tick data from Binance Futures via WebSocket, stores and aggregates the data locally, computes key quantitative analytics, and presents results through an interactive Streamlit dashboard.

The focus of the project is end-to-end system design — from data ingestion and storage to analytics and visualization — with an emphasis on modularity, extensibility, and clarity over production-scale optimization.

Key Features

Live tick data ingestion from Binance Futures (BTCUSDT, ETHUSDT)

Persistent local storage using DuckDB

Incremental resampling into OHLC bars (1s, 1m, 5m)

Statistical arbitrage analytics:

OLS hedge ratio estimation

Spread construction

Z-score computation

Rolling correlation

Augmented Dickey–Fuller (ADF) stationarity test

Interactive Streamlit dashboard with charts and controls

User-defined alerting (z-score threshold)

CSV export of processed OHLC data and analytics outputs

System Architecture & Design Philosophy

The application is intentionally structured into loosely coupled components:

Ingestion: Handles real-time WebSocket connections and buffering

Storage: Centralized data persistence using DuckDB

Resampling: Incremental aggregation of tick data into time-based OHLC bars

Analytics: Pure, stateless computation modules

Visualization: Streamlit-based UI layer

This separation ensures that:

New data sources (e.g., CSV uploads, alternative feeds) can be added with minimal changes

New analytics can be introduced without modifying ingestion or storage logic

The system remains readable, debuggable, and extensible

Although the application runs locally, the architecture mirrors how a scalable research or trading analytics stack would be structured.

Data Flow

Live Tick Ingestion
Binance Futures WebSocket streams trade-level data (timestamp, price, quantity).

Storage
Ticks are buffered and written to DuckDB tables for durability and analytical querying.

Resampling
Tick data is incrementally aggregated into OHLC bars at configurable timeframes (1s, 1m, 5m).

Analytics Computation
Analytics operate exclusively on resampled OHLC data:

Hedge ratio via OLS regression

Spread construction

Rolling z-score and correlation

Stationarity testing using ADF

Visualization & Interaction
Users interact through Streamlit controls to refresh analytics, change timeframes, adjust rolling windows, and export results.

Analytics Implemented
Hedge Ratio (OLS Regression)

An Ordinary Least Squares regression is used to estimate the hedge ratio between BTC and ETH prices. The slope coefficient is used to construct a hedged spread.

Spread & Z-Score

The spread is defined as:

Spread = BTC − β × ETH


The z-score measures how extreme the current spread is relative to its recent history using a rolling window.

Rolling Correlation

Rolling correlation between BTC and ETH prices is computed to observe time-varying dependency.

ADF Stationarity Test

An Augmented Dickey–Fuller test is provided to assess whether the constructed spread exhibits stationarity, which is critical for mean-reversion strategies.

Live Analytics Behavior

Data ingestion and resampling run continuously in the background.

Analytics are refreshed explicitly via a user-controlled “Refresh Analytics” action.

This design avoids unnecessary recomputation and UI instability while still enabling near-real-time inspection of signals such as z-score and correlation.

Different plots update at different logical frequencies depending on the selected timeframe and user interaction.

Data Export

The dashboard supports exporting processed data, not raw ticks:

Analytics CSV
Includes timestamps, prices, spread, z-score, and rolling correlation.

OHLC CSV
Includes OHLC bars for the selected timeframe.

CSV was chosen as the primary export format because it is universally supported in quantitative research workflows and can be directly consumed by tools such as Python, Excel, R, or MATLAB.

How to Run
Prerequisites

Python 3.10+

Internet access

Setup
git clone <repository-url>
cd quant-analytics-dashboard

python -m venv .venv
source .venv/bin/activate   # macOS/Linux
.\.venv\Scripts\Activate.ps1  # Windows

python -m pip install -r requirements.txt

Run the App
streamlit run app.py


Open the dashboard at:
http://localhost:8501

Limitations & Future Extensions

The system is designed as a research prototype, not a production trading engine.

No execution or order management logic is included.

Live UI updates are user-triggered for stability.

Potential future extensions:

Kalman filter–based dynamic hedge ratios

Robust regression methods

Mean-reversion backtesting

Liquidity filters and cross-correlation heatmaps

Alternative data sources (CSV, REST APIs)

ChatGPT Usage Transparency

ChatGPT was used as a development aid for:

Architectural structuring

Debugging Python, DuckDB, and Streamlit issues

Refining analytics logic

Improving code organization and documentation

All design decisions, implementation choices, and final code integration were reviewed and controlled by the author.

Author

Samarth Arole
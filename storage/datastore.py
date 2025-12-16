# storage/datastore.py

import duckdb
import pandas as pd
from pathlib import Path

class MarketDataStore:
    def __init__(self, db_path="data/market.duckdb"):
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self.con = duckdb.connect(db_path)
        self._create_tables()

    def _create_tables(self):
        self.con.execute("""
            CREATE TABLE IF NOT EXISTS ticks (
                ts TIMESTAMP,
                symbol VARCHAR,
                price DOUBLE,
                size DOUBLE
            )
        """)

        self.con.execute("""
            CREATE TABLE IF NOT EXISTS ohlc (
                ts TIMESTAMP,
                symbol VARCHAR,
                timeframe VARCHAR,
                open DOUBLE,
                high DOUBLE,
                low DOUBLE,
                close DOUBLE,
                volume DOUBLE
            )
        """)

    # ---------- INSERT METHODS ----------

    def insert_ticks(self, df: pd.DataFrame):
        """
        Expects columns: ts, symbol, price, size
        """
        self.con.register("ticks_df", df)
        self.con.execute("INSERT INTO ticks SELECT * FROM ticks_df")

    def insert_ohlc(self, df: pd.DataFrame):
        """
        Expects columns:
        ts, symbol, timeframe, open, high, low, close, volume
        """
        self.con.register("ohlc_df", df)
        self.con.execute("INSERT INTO ohlc SELECT * FROM ohlc_df")

    # ---------- QUERY METHODS ----------

    
    
    def get_ticks(self, symbol, limit=100):
        query = """
            SELECT *
            FROM ticks
            WHERE symbol = ?
            ORDER BY ts DESC
            LIMIT ?
        """
        return self.con.execute(query, [symbol, limit]).fetchdf()


    def get_ohlc(self, symbol, timeframe, lookback_minutes=60):
        query = f"""
            SELECT *
            FROM ohlc
            WHERE symbol = '{symbol}'
            AND timeframe = '{timeframe}'
            AND ts >= NOW() - INTERVAL {lookback_minutes} MINUTE
            ORDER BY ts
        """
        return self.con.execute(query).fetchdf()

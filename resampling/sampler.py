# resampling/sampler.py

import duckdb
import pandas as pd

TIMEFRAME_MAP = {
    "1s": "1 second",
    "1m": "1 minute",
    "5m": "5 minutes"
}

class Resampler:
    def __init__(self, datastore):
        self.con = datastore.con

    def _latest_bar_time(self, symbol, timeframe):
        result = self.con.execute(
            """
            SELECT MAX(ts)
            FROM ohlc
            WHERE symbol = ? AND timeframe = ?
            """,
            [symbol, timeframe]
        ).fetchone()[0]

        return result

    def resample(self, symbol, timeframe):
        interval = TIMEFRAME_MAP[timeframe]
        last_ts = self._latest_bar_time(symbol, timeframe)

        where_clause = ""
        params = [symbol]

        if last_ts is not None:
            where_clause = "AND ts > ?"
            params.append(last_ts)

        query = f"""
        INSERT INTO ohlc
        SELECT
            time_bucket(INTERVAL '{interval}', ts) AS ts,
            symbol,
            '{timeframe}' AS timeframe,
            arg_min(price, ts) AS open,
            max(price) AS high,
            min(price) AS low,
            arg_max(price, ts) AS close,
            sum(size) AS volume
        FROM ticks
        WHERE symbol = ?
        {where_clause}
        GROUP BY 1, 2
        ORDER BY 1
        """


        self.con.execute(query, params)

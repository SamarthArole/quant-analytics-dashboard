# ingestion/binance_ws.py

import json
import threading
import time
import websocket
import pandas as pd
from datetime import datetime, timezone

class BinanceWebSocketIngestor:
    def __init__(self, symbols, datastore, flush_interval=1.0):
        """
        symbols: list of strings, e.g. ['btcusdt', 'ethusdt']
        datastore: MarketDataStore instance
        flush_interval: seconds
        """
        self.symbols = symbols
        self.datastore = datastore
        self.flush_interval = flush_interval

        self._buffer = []
        self._lock = threading.Lock()
        self._running = False
        self._threads = []

    # ---------- WebSocket Callbacks ----------

    def _on_message(self, ws, message):
        try:
            data = json.loads(message)
            if data.get("e") != "trade":
                return

            tick = {
                "ts": datetime.fromtimestamp(data["T"] / 1000, tz=timezone.utc),
                "symbol": data["s"].lower(),
                "price": float(data["p"]),
                "size": float(data["q"])
            }

            with self._lock:
                self._buffer.append(tick)

        except Exception:
            pass

    def _on_error(self, ws, error):
        print("WebSocket error:", error)

    def _on_close(self, ws, close_status_code, close_msg):
        print("WebSocket closed:", close_status_code, close_msg)

    def _on_open(self, ws):
        print("WebSocket connected")

    # ---------- Worker Threads ----------

    def _start_socket(self, symbol):
        url = f"wss://fstream.binance.com/ws/{symbol}@trade"
        ws = websocket.WebSocketApp(
            url,
            on_message=self._on_message,
            on_error=self._on_error,
            on_close=self._on_close,
            on_open=self._on_open
        )
        ws.run_forever()

    def _flush_loop(self):
        while self._running:
            time.sleep(self.flush_interval)
            self._flush_buffer()

    def _flush_buffer(self):
        with self._lock:
            if not self._buffer:
                return
            df = pd.DataFrame(self._buffer)
            self._buffer = []

        if not df.empty:
            self.datastore.insert_ticks(df)

    # ---------- Public API ----------

    def start(self):
        if self._running:
            return

        self._running = True

        # WebSocket threads (one per symbol)
        for sym in self.symbols:
            t = threading.Thread(target=self._start_socket, args=(sym,), daemon=True)
            t.start()
            self._threads.append(t)

        # Flush thread
        flush_thread = threading.Thread(target=self._flush_loop, daemon=True)
        flush_thread.start()
        self._threads.append(flush_thread)

        print("Binance ingestion started.")

    def stop(self):
        self._running = False
        print("Binance ingestion stopped.")

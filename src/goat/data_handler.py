from datetime import datetime
from typing import Iterator, Protocol

import numpy as np
import polars as pl
from pydantic import BaseModel, Field
from pydantic_settings import SettingsConfigDict


class Candle(BaseModel):
    start_timestamp: int = Field(default=0, ge=0)
    time_period: int = Field(default=0, ge=0)
    open: float = np.nan
    high: float = -np.inf
    low: float = np.inf
    close: float = np.nan
    volume: int = Field(default=0, ge=0)
    tick_count: int = Field(default=0, ge=0)

    def __str__(self) -> str:
        return "Tick %2d - %s | O:%.2f H:%.2f L:%.2f C:%.2f V:%-8d" % (
            self.tick_count,
            datetime.fromtimestamp(self.start_timestamp / 1_000_000_000),
            self.open,
            self.high,
            self.low,
            self.close,
            self.volume,
        )

    model_config = SettingsConfigDict(extra="ignore")


class CandleDataHandler(Protocol):
    def next_candle(self) -> Candle | None: ...


class HistoricDataHandler(BaseModel):
    """Historic data handler."""

    df: pl.DataFrame | pl.LazyFrame | None = None
    next_candle_index: int = Field(default=0, ge=0)

    # def __init__(self, df: pl.DataFrame | pl.LazyFrame | None = None, next_candle_index: int = 0):
    #     self.df = df
    #     self.next_candle_index = next_candle_index

    def next_candle(self) -> Candle | None:
        if self.df is None:
            return None
        elif isinstance(self.df, pl.LazyFrame):
            self.df = self.df.collect()
        if self.next_candle_index >= len(self.df):
            return None
        next_candle = Candle(**self.df.row(index=self.next_candle_index, named=True))
        self.next_candle_index += 1
        return next_candle

    model_config = SettingsConfigDict(arbitrary_types_allowed=True)


def process_candles(handler: CandleDataHandler) -> None:
    while True:
        candle = handler.next_candle()
        if candle is None:
            break
        print(candle)


class StreamDataHandler:
    """Stream data handler."""

    data_stream: Iterator[Candle]

    def __init__(self, data_stream: Iterator[Candle]):
        self.data_stream = data_stream

    def next_candle(self) -> Candle | None:
        try:
            return next(self.data_stream)
        except StopIteration:
            return None


if __name__ == "__main__":
    candle = Candle(start_timestamp=0, time_period=60 * 1_000_000_000)
    print(candle)
    df = pl.DataFrame(
        {
            "start_timestamp": [0, 60 * 1_000_000_000],
            "time_period": [60 * 1_000_000_000] * 2,
            "open": [np.nan, 1.23],
            "high": [-np.inf, 2.34],
            "low": [np.inf, 1.22],
            "close": [np.nan, 2.34],
            "volume": [0, 100],
            "tick_count": [0, 1],
            "symbol": ["AAPL"] * 2,
        }
    )
    print(df)
    handler = HistoricDataHandler(df=df)
    process_candles(handler)

    stream_handler = StreamDataHandler(
        data_stream=iter(
            [
                Candle(start_timestamp=0, time_period=60 * 1_000_000_000),
                Candle(
                    start_timestamp=60 * 1_000_000_000,
                    time_period=60 * 1_000_000_000,
                    open=1.23,
                    high=2.34,
                    low=1.22,
                    close=2.34,
                    volume=100,
                    tick_count=1,
                    symbol="AAPL",  # type: ignore[argument]
                ),
            ]
        )
    )
    process_candles(stream_handler)

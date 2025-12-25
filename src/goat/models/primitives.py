from typing import Annotated, Self, overload

import numpy as np
from pydantic import BaseModel, Field, model_validator

# Timestamp in nanoseconds since the Unix epoch
MIN_TIMESTAMP_NS = 0
MAX_TIMESTAMP_NS = 2**64 - 1
Timestamp = Annotated[int, Field(ge=MIN_TIMESTAMP_NS, le=MAX_TIMESTAMP_NS)]

# Volume (always non-negative)
Volume = Annotated[int, Field(gt=0)]


class Tick(BaseModel):
    timestamp: Timestamp
    price: float = Field(description="Price in USD")
    volume: Volume = Field(description="Volume")


class BaseCandle(BaseModel):
    open: float = Field(default=np.nan, description="Open price in USD")
    high: float = Field(default=-np.inf, description="High price in USD")
    low: float = Field(default=np.inf, description="Low price in USD")
    close: float = Field(default=np.nan, description="Close price in USD")
    volume: Volume = Field(default=0, description="Volume")


class TimeWindowCandle(BaseCandle):
    start_timestamp: Timestamp
    end_timestamp: Timestamp

    @model_validator(mode="after")
    def validate_timestamps(self):
        if self.start_timestamp > self.end_timestamp:
            raise ValueError("start_timestamp must be less than or equal to end_timestamp")
        return self

    @overload
    def update(self, tick: Tick) -> None: ...

    @overload
    def update(self, candle: Self) -> None: ...

    def update(self, data: Tick | Self) -> None:
        if isinstance(data, Tick):
            self._update_from_tick(data)
        elif isinstance(data, TimeWindowCandle):
            self._update_from_candle(data)
        else:
            raise TypeError("data must be a Tick or a Candle")

    def _update_from_tick(self, tick: Tick) -> None:
        if not (self.start_timestamp <= tick.timestamp <= self.end_timestamp):
            raise ValueError("Tick timestamp is outside the candle time window")

        if np.isnan(self.open):
            self.open = tick.price
        self.high = max(self.high, tick.price)
        self.low = min(self.low, tick.price)
        self.close = tick.price
        self.volume += tick.volume

    def _update_from_candle(self, candle: Self) -> None:
        if self.start_timestamp > candle.start_timestamp or self.end_timestamp < candle.end_timestamp:
            raise ValueError("New candle time window is outside the candle time window")
        if self.start_timestamp == candle.start_timestamp:
            if np.isnan(self.open):
                self.open = candle.open
            elif not np.isnan(candle.open) and not np.isclose(self.open, candle.open):
                raise ValueError("Candle open price is different")
        if self.end_timestamp == candle.end_timestamp:
            if np.isnan(self.close):
                self.close = candle.close
            elif not np.isnan(candle.close) and not np.isclose(self.close, candle.close):
                raise ValueError("Candle close price is different")
        self.high = max(self.high, candle.high)
        self.low = min(self.low, candle.low)
        self.volume += candle.volume

    def __str__(self):
        return f"Candle(start={self.start_timestamp}, end={self.end_timestamp}, open={self.open}, high={self.high}, low={self.low}, close={self.close}, volume={self.volume})"


class FixedTickCountCandle(BaseCandle):
    start_timestamp: Timestamp
    max_tick_count: int = Field(description="Maximum number of ticks", default=0)
    tick_count: int = Field(description="Number of ticks", default=0)

    # Add if needed
    # ticks: list[Tick] = Field(description="List of ticks")

    def update(self, tick: Tick):
        if self.tick_count >= self.max_tick_count:
            raise ValueError("Candle is full")

        if self.start_timestamp > tick.timestamp:
            raise ValueError("Tick timestamp is before the candle start timestamp")

        if np.isnan(self.open):
            self.open = tick.price
        self.high = max(self.high, tick.price)
        self.low = min(self.low, tick.price)
        self.close = tick.price
        self.volume += tick.volume
        self.tick_count += 1
        # self.ticks.append(tick)

    def __str__(self):
        return f"Candle(start={self.start_timestamp}, max_tick_count={self.max_tick_count}, tick_count={self.tick_count}, open={self.open}, high={self.high}, low={self.low}, close={self.close}, volume={self.volume})"


if __name__ == "__main__":
    ts = 1
    print(ts)
    candle = TimeWindowCandle(start_timestamp=ts, end_timestamp=ts)
    print(candle)
    candle.update(Tick(timestamp=ts, price=1, volume=1))
    print(candle)

from typing import Annotated, Self, overload

import numpy as np
from pydantic import BaseModel, Field, model_validator

# Timestamp in nanoseconds since the Unix epoch
MIN_TIMESTAMP_NS = 0
MAX_TIMESTAMP_NS = 2**64 - 1
Timestamp = Annotated[int, Field(ge=MIN_TIMESTAMP_NS, le=MAX_TIMESTAMP_NS)]

# Volume (always non-negative)
Volume = Annotated[int, Field(ge=0)]


class Tick(BaseModel):
    timestamp: Timestamp
    price: float = Field(description="Price in USD")
    volume: Volume = Field(description="Volume")


class Candle(BaseModel):
    open: float = Field(default=np.nan, description="Open price in USD")
    high: float = Field(default=-np.inf, description="High price in USD")
    low: float = Field(default=np.inf, description="Low price in USD")
    close: float = Field(default=np.nan, description="Close price in USD")
    volume: Volume = Field(default=0, description="Volume")

    def __str__(self):
        return f"Candle(open={self.open}, high={self.high}, low={self.low}, close={self.close}, volume={self.volume})"


class TimeCandle(Candle):
    start_timestamp: Timestamp
    end_timestamp: Timestamp

    @model_validator(mode="after")
    def validate_timestamps(self):
        if self.start_timestamp > self.end_timestamp:
            raise ValueError("Candle start_timestamp must be less than or equal to end_timestamp")
        return self

    @overload
    def update(self, tick: Tick) -> None: ...

    @overload
    def update(self, candle: Self) -> None: ...

    def update(self, data: Tick | Self) -> None:
        if isinstance(data, Tick):
            self._update_from_tick(data)
        elif isinstance(data, TimeCandle):
            self._update_from_candle(data)
        else:
            raise TypeError("Update data must be a Tick or a Candle")

    def _update_from_tick(self, tick: Tick) -> None:
        if not (self.start_timestamp <= tick.timestamp <= self.end_timestamp):
            raise ValueError("Tick timestamp is outside the candle time window")
        if np.isnan(self.open):
            self.open = tick.price
        self.close = tick.price
        self.high = max(self.high, tick.price)
        self.low = min(self.low, tick.price)
        self.volume += tick.volume

    def _update_from_candle(self, candle: Self) -> None:
        if self.start_timestamp > candle.start_timestamp or self.end_timestamp < candle.end_timestamp:
            raise ValueError("New candle time window is outside the candle time window")
        if np.isnan(self.open):
            self.open = candle.open
        if np.isnan(self.close):
            self.close = candle.close
        if self.start_timestamp == candle.start_timestamp and not np.isclose(self.open, candle.open):
            raise ValueError(f"Candle open price is different: expected {self.open}, got {candle.open}")
        if self.end_timestamp == candle.end_timestamp and not np.isclose(self.close, candle.close):
            raise ValueError(f"Candle close price is different: expected {self.close}, got {candle.close}")
        self.high = max(self.high, candle.high)
        self.low = min(self.low, candle.low)
        self.volume += candle.volume

    def __str__(self):
        return f"TimeCandle(start={self.start_timestamp}, end={self.end_timestamp}, {super().__str__()})"


class TickCandle(Candle):
    start_timestamp: Timestamp
    max_ticks: int = Field(description="Maximum number of ticks", gt=0)
    num_ticks: int = Field(description="Number of ticks", default=0)
    last_timestamp: Timestamp | None = Field(description="Timestamp of the last (youngest) tick", default=None)

    @model_validator(mode="after")
    def validate_tick_count(self):
        if self.num_ticks > self.max_ticks:
            raise ValueError("Tick count is greater than maximum tick count")
        return self

    def update(self, tick: Tick) -> None:
        if self.start_timestamp > tick.timestamp:
            raise ValueError("Tick timestamp is before the candle start timestamp")

        if self.num_ticks >= self.max_ticks:
            raise ValueError("TickCandle is full")

        if np.isnan(self.open):
            self.open = tick.price
        self.high = max(self.high, tick.price)
        self.low = min(self.low, tick.price)
        if self.last_timestamp is None or self.last_timestamp <= tick.timestamp:
            self.close = tick.price
            self.last_timestamp = tick.timestamp
        self.volume += tick.volume
        self.num_ticks += 1

    def __str__(self):
        return (
            f"TickCandle(start={self.start_timestamp}, max_ticks={self.max_ticks}, "
            f"num_ticks={self.num_ticks}, {super().__str__()})"
        )

from enum import StrEnum
from typing import Callable, Protocol

from goat.data_handler import Candle
from goat.enums import Action, Symbol


class StrategyID(StrEnum):
    MOVING_AVERAGE_CROSS = "moving_average_cross"


class Strategy(Protocol):
    """Protocol defining the interface for trading strategies.

    Strategies receive market data and generate trading signals.
    They can optionally emit signals via an on_signal callback.
    """

    id: StrategyID
    symbol: Symbol
    on_signal: Callable[[object], None] | None  # SignalEvent callback

    def calculate_signal(self, candle: Candle) -> Action | None:
        """Calculate trading signal from new price data.

        Args:
            candle: The latest candle.

        Returns:
            Action.BUY, Action.SELL, or None if no signal.
        """
        ...

    def run(self) -> None:
        """Start the strategy."""
        ...

    def stop(self) -> None:
        """Stop the strategy."""
        ...


class MovingAverageCrossStrategy:
    """Moving average crossover strategy.

    Generates BUY signals when short MA crosses above long MA,
    and SELL signals when short MA crosses below long MA.
    """

    id = StrategyID.MOVING_AVERAGE_CROSS

    def __init__(
        self,
        short_window: int,
        long_window: int,
        symbol: Symbol,
        on_signal: Callable[[object], None] | None = None,
    ):
        if short_window >= long_window:
            raise ValueError("short_window must be less than long_window")
        self.short_window = short_window
        self.long_window = long_window
        self.symbol = symbol
        self.on_signal = on_signal
        self._price_history: list[float] = []
        self._prev_short_ma: float | None = None
        self._prev_long_ma: float | None = None

    def calculate_signal(self, candle: Candle) -> Action | None:
        """Calculate signal based on moving average crossover.

        Args:
            candle: The latest candle.

        Returns:
            Action.BUY on golden cross, Action.SELL on death cross, None otherwise.
        """
        self._price_history.append(candle.close)

        # Need enough data for long window
        if len(self._price_history) < self.long_window:
            return None

        # Calculate current moving averages
        short_ma = sum(self._price_history[-self.short_window :]) / self.short_window
        long_ma = sum(self._price_history[-self.long_window :]) / self.long_window

        signal: Action | None = None

        # Check for crossover (need previous values)
        if self._prev_short_ma is not None and self._prev_long_ma is not None:
            # Golden cross: short MA crosses above long MA
            if self._prev_short_ma <= self._prev_long_ma and short_ma > long_ma:
                signal = Action.BUY
            # Death cross: short MA crosses below long MA
            elif self._prev_short_ma >= self._prev_long_ma and short_ma < long_ma:
                signal = Action.SELL

        # Store for next iteration
        self._prev_short_ma = short_ma
        self._prev_long_ma = long_ma

        # Keep only necessary history
        max_history = self.long_window + 1
        if len(self._price_history) > max_history:
            self._price_history = self._price_history[-max_history:]

        return signal

    def run(self) -> None:
        """Start the strategy (reset state)."""
        self._price_history = []
        self._prev_short_ma = None
        self._prev_long_ma = None

    def stop(self) -> None:
        """Stop the strategy."""
        pass


if __name__ == "__main__":
    strategy = MovingAverageCrossStrategy(
        short_window=10,
        long_window=30,
        symbol=Symbol.AAPL,
    )
    strategy.run()

    # Simulate price data
    import random

    random.seed(42)
    price = 100.0
    for i in range(50):
        price += random.uniform(-2, 2)
        signal = strategy.calculate_signal(Candle(close=price))
        if signal:
            print(f"Day {i}: Price={price:.2f}, Signal={signal}")

    strategy.stop()

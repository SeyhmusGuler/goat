from enum import StrEnum
from typing import Protocol

from goat.enums import Symbol


class StrategyID(StrEnum):
    MOVING_AVERAGE_CROSS = "moving_average_cross"


class Strategy(Protocol):
    id: StrategyID

    def run(self) -> None:
        raise NotImplementedError

    def stop(self) -> None:
        raise NotImplementedError


class MovingAverageCrossStrategy:
    id = StrategyID.MOVING_AVERAGE_CROSS

    def __init__(
        self,
        short_window: int,
        long_window: int,
        symbol: Symbol,
    ):
        self.short_window = short_window
        self.long_window = long_window
        self.symbol = symbol

    def run(self) -> None:
        pass

    def stop(self) -> None:
        pass


if __name__ == "__main__":
    strategy = MovingAverageCrossStrategy(
        short_window=10,
        long_window=30,
        symbol=Symbol.AAPL,
    )
    strategy.run()
    strategy.stop()

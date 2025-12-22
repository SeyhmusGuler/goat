from argparse import Action
from goat.strategy import StrategyID
from pydantic import BaseModel
from typing import Literal
from goat.enums import DateTime, Symbol


class Event(BaseModel):
    """Base class for events."""

    type: Literal["MARKET", "SIGNAL", "ORDER", "FILL"]


class MarketEvent(Event):
    """Market event."""

    def __init__(self) -> None:
        super().__init__(type="MARKET")


class SignalEvent(Event):
    """Signal event."""

    def __init__(
        self,
        strategy_id: StrategyID,
        symbol: Symbol,
        action: Action,
        datetime: DateTime,
    ) -> None:
        super().__init__(type="SIGNAL")
        self.strategy_id = strategy_id
        self.symbol = symbol
        self.action = action
        self.datetime = datetime


class OrderEvent(Event):
    """Order event."""

    def __init__(self) -> None:
        super().__init__(type="ORDER")


class FillEvent(Event):
    """Fill event."""

    def __init__(self) -> None:
        super().__init__(type="FILL")

from __future__ import annotations
from typing import TYPE_CHECKING

from argparse import Action
from goat.strategy import StrategyID
from pydantic import BaseModel
from typing import Literal
from goat.enums import DateTime, Symbol


if TYPE_CHECKING:
    from goat.settings import Settings  # Only for type checker, not imported at runtime


class EventForTypeChecking:
    def __init__(self, name: str, settings: Settings | None = None):
        self.name = name
        self._settings = settings

    def process(self) -> None:
        if self._settings is None:
            from goat.settings import load_settings  # Actual runtime import

            self._settings = load_settings()

        print(f"Processing {self.name} in {self._settings.APP_MODE} mode")


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

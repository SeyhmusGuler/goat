import uuid
from typing import TYPE_CHECKING, Literal

from pydantic import AwareDatetime, BaseModel, Field

from goat.enums import Action, Direction, OrderType, Symbol
from goat.strategy import StrategyID

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

    event_type: Literal["MARKET", "SIGNAL", "ORDER", "FILL"] = Field(..., alias="type")


class MarketEvent(Event):
    """Market event."""

    event_type: Literal["MARKET"] = "MARKET"


class SignalEvent(Event):
    """Signal event."""

    event_type: Literal["SIGNAL"] = "SIGNAL"
    strategy_id: StrategyID
    symbol: Symbol
    action: Action
    datetime: AwareDatetime


class OrderEvent(Event):
    """Order event."""

    event_type: Literal["ORDER"] = "ORDER"
    order_id: uuid.UUID = Field(default_factory=uuid.uuid4)
    symbol: Symbol
    direction: Direction
    order_type: OrderType
    quantity: int = Field(..., gt=0)
    price: float


class FillEvent(Event):
    """Fill event."""

    event_type: Literal["FILL"] = "FILL"
    fill_type: Literal["PARTIAL", "FULL"]
    order_id: uuid.UUID
    quantity: int = Field(..., gt=0)
    price: float
    datetime: AwareDatetime
    fill_cost: float = Field(default=0.0)
    commission: float = Field(default=0.0)


if __name__ == "__main__":
    from datetime import datetime, timezone

    event = MarketEvent()
    print(event)
    order_event = OrderEvent(
        symbol=Symbol("AAPL"),
        direction=Direction.BUY,
        order_type=OrderType.LIMIT,
        quantity=10,
        price=100.0,
    )
    fill_event = FillEvent(
        fill_type="PARTIAL",
        order_id=order_event.order_id,
        quantity=5,
        price=100.0,
        datetime=datetime.now(tz=timezone.utc),
    )
    print(order_event)
    print(fill_event)

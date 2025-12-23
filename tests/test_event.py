import pytest

from pydantic import ValidationError
from goat.event import OrderEvent, FillEvent
from goat.enums import Symbol, Direction, OrderType
import uuid
from datetime import datetime, timezone


class TestOrderEvent:
    def test_order_event_success(self):
        order_event = OrderEvent(
            symbol=Symbol("AAPL"),
            direction=Direction.BUY,
            order_type=OrderType.LIMIT,
            quantity=10,
            price=100.0,
        )
        assert order_event.symbol == Symbol("AAPL")
        assert order_event.direction == Direction.BUY
        assert order_event.order_type == OrderType.LIMIT
        assert order_event.quantity == 10
        assert order_event.price == 100.0

    @pytest.mark.parametrize("quantity", [0, -1, 1.1], ids=["zero", "negative", "float"])
    def test_order_event_raises_quantity_error(self, quantity):
        with pytest.raises(ValidationError):
            OrderEvent(
                symbol=Symbol("AAPL"),
                direction=Direction.BUY,
                order_type=OrderType.LIMIT,
                quantity=quantity,
                price=100.0,
            )


class TestFillEvent:
    def test_fill_event_success(self):
        fill_event = FillEvent(
            fill_type="PARTIAL",
            order_id=uuid.uuid4(),
            quantity=5,
            price=100.0,
            datetime=datetime.now(tz=timezone.utc),
        )
        assert fill_event.fill_type == "PARTIAL"
        assert fill_event.order_id is not None
        assert fill_event.quantity == 5
        assert fill_event.price == 100.0
        assert fill_event.datetime is not None

    with pytest.raises(ValidationError):
        _ = FillEvent(
            fill_type="PARTIAL",
            order_id=uuid.uuid4(),
            quantity=5,
            price=100.0,
            datetime=datetime.now(),
        )

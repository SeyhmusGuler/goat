"""Tests for the execution module."""

import uuid

import pytest

from goat.enums import Direction, ExecutionPolicyType, OrderStatus, OrderType, Symbol
from goat.execution import (
    ExecutionHandler,
    IcebergPolicy,
    ImmediatePolicy,
    Order,
    OrderBook,
    TWAPPolicy,
    get_execution_policy,
)


class TestOrder:
    """Tests for the Order model."""

    def test_order_creation(self):
        """Test basic order creation."""
        order = Order(
            symbol=Symbol.AAPL,
            direction=Direction.BUY,
            order_type=OrderType.LIMIT,
            quantity=100,
            remaining_quantity=100,
            price=150.0,
        )
        assert order.symbol == Symbol.AAPL
        assert order.direction == Direction.BUY
        assert order.quantity == 100
        assert order.remaining_quantity == 100
        assert order.status == OrderStatus.PENDING
        assert order.order_id is not None

    def test_order_apply_fill_partial(self):
        """Test partial fill application."""
        order = Order(
            symbol=Symbol.AAPL,
            direction=Direction.BUY,
            order_type=OrderType.LIMIT,
            quantity=100,
            remaining_quantity=100,
            price=150.0,
        )
        fill = order.apply_fill(30, 149.5)

        assert order.remaining_quantity == 70
        assert order.status == OrderStatus.PARTIALLY_FILLED
        assert fill.quantity == 30
        assert fill.price == 149.5
        assert len(order.fills) == 1

    def test_order_apply_fill_complete(self):
        """Test complete fill application."""
        order = Order(
            symbol=Symbol.AAPL,
            direction=Direction.BUY,
            order_type=OrderType.LIMIT,
            quantity=100,
            remaining_quantity=100,
            price=150.0,
        )
        order.apply_fill(100, 150.0)

        assert order.remaining_quantity == 0
        assert order.status == OrderStatus.FILLED
        assert order.is_complete is True

    def test_order_average_fill_price(self):
        """Test average fill price calculation."""
        order = Order(
            symbol=Symbol.AAPL,
            direction=Direction.BUY,
            order_type=OrderType.LIMIT,
            quantity=100,
            remaining_quantity=100,
            price=150.0,
        )
        order.apply_fill(60, 149.0)
        order.apply_fill(40, 151.0)

        # (60*149 + 40*151) / 100 = (8940 + 6040) / 100 = 149.8
        assert order.average_fill_price == pytest.approx(149.8)

    def test_order_fill_exceeds_remaining_raises(self):
        """Test that filling more than remaining raises error."""
        order = Order(
            symbol=Symbol.AAPL,
            direction=Direction.BUY,
            order_type=OrderType.LIMIT,
            quantity=100,
            remaining_quantity=100,
            price=150.0,
        )
        order.apply_fill(60, 150.0)

        with pytest.raises(ValueError, match="exceeds remaining"):
            order.apply_fill(50, 150.0)


class TestOrderBook:
    """Tests for the OrderBook matching engine."""

    def test_add_buy_order_no_match(self):
        """Test adding a buy order with no matching sell."""
        book = OrderBook(Symbol.AAPL)
        order = Order(
            symbol=Symbol.AAPL,
            direction=Direction.BUY,
            order_type=OrderType.LIMIT,
            quantity=100,
            remaining_quantity=100,
            price=150.0,
        )
        fills = book.add_order(order)

        assert len(fills) == 0
        assert book.best_bid == 150.0
        assert book.best_ask is None

    def test_add_sell_order_no_match(self):
        """Test adding a sell order with no matching buy."""
        book = OrderBook(Symbol.AAPL)
        order = Order(
            symbol=Symbol.AAPL,
            direction=Direction.SELL,
            order_type=OrderType.LIMIT,
            quantity=100,
            remaining_quantity=100,
            price=155.0,
        )
        fills = book.add_order(order)

        assert len(fills) == 0
        assert book.best_ask == 155.0
        assert book.best_bid is None

    def test_match_exact_quantity(self):
        """Test matching orders with exact quantities."""
        book = OrderBook(Symbol.AAPL)

        # Add resting sell order
        sell_order = Order(
            symbol=Symbol.AAPL,
            direction=Direction.SELL,
            order_type=OrderType.LIMIT,
            quantity=100,
            remaining_quantity=100,
            price=150.0,
        )
        book.add_order(sell_order)

        # Add matching buy order
        buy_order = Order(
            symbol=Symbol.AAPL,
            direction=Direction.BUY,
            order_type=OrderType.LIMIT,
            quantity=100,
            remaining_quantity=100,
            price=150.0,
        )
        fills = book.add_order(buy_order)

        assert len(fills) == 2  # One for each side
        assert buy_order.status == OrderStatus.FILLED
        assert sell_order.status == OrderStatus.FILLED
        assert book.best_bid is None
        assert book.best_ask is None

    def test_match_partial_quantity(self):
        """Test matching orders with different quantities."""
        book = OrderBook(Symbol.AAPL)

        # Add resting sell order for 50 shares
        sell_order = Order(
            symbol=Symbol.AAPL,
            direction=Direction.SELL,
            order_type=OrderType.LIMIT,
            quantity=50,
            remaining_quantity=50,
            price=150.0,
        )
        book.add_order(sell_order)

        # Add buy order for 100 shares
        buy_order = Order(
            symbol=Symbol.AAPL,
            direction=Direction.BUY,
            order_type=OrderType.LIMIT,
            quantity=100,
            remaining_quantity=100,
            price=150.0,
        )
        fills = book.add_order(buy_order)

        assert len(fills) == 2
        assert sell_order.status == OrderStatus.FILLED
        assert buy_order.status == OrderStatus.PARTIALLY_FILLED
        assert buy_order.remaining_quantity == 50
        assert book.best_bid == 150.0  # Remaining buy order

    def test_price_priority(self):
        """Test that better prices match first."""
        book = OrderBook(Symbol.AAPL)

        # Add two sell orders at different prices
        sell_high = Order(
            symbol=Symbol.AAPL,
            direction=Direction.SELL,
            order_type=OrderType.LIMIT,
            quantity=100,
            remaining_quantity=100,
            price=152.0,
        )
        sell_low = Order(
            symbol=Symbol.AAPL,
            direction=Direction.SELL,
            order_type=OrderType.LIMIT,
            quantity=100,
            remaining_quantity=100,
            price=150.0,
        )
        book.add_order(sell_high)
        book.add_order(sell_low)

        # Add buy order that can match the lower-priced sell
        buy_order = Order(
            symbol=Symbol.AAPL,
            direction=Direction.BUY,
            order_type=OrderType.LIMIT,
            quantity=100,
            remaining_quantity=100,
            price=151.0,
        )
        fills = book.add_order(buy_order)

        # Should match the lower price
        assert len(fills) == 2
        assert sell_low.status == OrderStatus.FILLED
        assert sell_high.status == OrderStatus.OPEN  # Not matched
        assert buy_order.status == OrderStatus.FILLED
        assert fills[0].price == 150.0  # Matched at resting order price

    def test_cancel_order(self):
        """Test order cancellation."""
        book = OrderBook(Symbol.AAPL)
        order = Order(
            symbol=Symbol.AAPL,
            direction=Direction.BUY,
            order_type=OrderType.LIMIT,
            quantity=100,
            remaining_quantity=100,
            price=150.0,
        )
        book.add_order(order)

        result = book.cancel_order(order.order_id)

        assert result is True
        assert order.status == OrderStatus.CANCELLED
        assert book.best_bid is None

    def test_cancel_nonexistent_order(self):
        """Test cancelling an order that doesn't exist."""
        book = OrderBook(Symbol.AAPL)
        result = book.cancel_order(uuid.uuid4())
        assert result is False


class TestExecutionPolicy:
    """Tests for execution policies."""

    def test_immediate_policy(self):
        """Test immediate policy returns order unchanged."""
        policy = ImmediatePolicy()
        order = Order(
            symbol=Symbol.AAPL,
            direction=Direction.BUY,
            order_type=OrderType.LIMIT,
            quantity=1000,
            remaining_quantity=1000,
            price=150.0,
        )
        chunks = policy.split_order(order)

        assert len(chunks) == 1
        assert chunks[0] is order

    def test_twap_policy_splits_order(self):
        """Test TWAP policy splits order into chunks."""
        policy = TWAPPolicy(num_chunks=5)
        order = Order(
            symbol=Symbol.AAPL,
            direction=Direction.BUY,
            order_type=OrderType.LIMIT,
            quantity=1000,
            remaining_quantity=1000,
            price=150.0,
        )
        chunks = policy.split_order(order)

        assert len(chunks) == 5
        total_qty = sum(c.quantity for c in chunks)
        assert total_qty == 1000
        # Each chunk should be 200
        for chunk in chunks:
            assert chunk.quantity == 200

    def test_twap_policy_handles_remainder(self):
        """Test TWAP policy distributes remainder correctly."""
        policy = TWAPPolicy(num_chunks=3)
        order = Order(
            symbol=Symbol.AAPL,
            direction=Direction.BUY,
            order_type=OrderType.LIMIT,
            quantity=100,
            remaining_quantity=100,
            price=150.0,
        )
        chunks = policy.split_order(order)

        assert len(chunks) == 3
        total_qty = sum(c.quantity for c in chunks)
        assert total_qty == 100
        # 100 / 3 = 33 with remainder 1
        assert chunks[0].quantity == 34  # Gets remainder
        assert chunks[1].quantity == 33
        assert chunks[2].quantity == 33

    def test_twap_policy_small_quantity(self):
        """Test TWAP policy doesn't split small quantities."""
        policy = TWAPPolicy(num_chunks=5)
        order = Order(
            symbol=Symbol.AAPL,
            direction=Direction.BUY,
            order_type=OrderType.LIMIT,
            quantity=3,
            remaining_quantity=3,
            price=150.0,
        )
        chunks = policy.split_order(order)

        assert len(chunks) == 1
        assert chunks[0] is order

    def test_iceberg_policy(self):
        """Test iceberg policy splits into visible chunks."""
        policy = IcebergPolicy(visible_quantity=100)
        order = Order(
            symbol=Symbol.AAPL,
            direction=Direction.BUY,
            order_type=OrderType.LIMIT,
            quantity=350,
            remaining_quantity=350,
            price=150.0,
        )
        chunks = policy.split_order(order)

        assert len(chunks) == 4
        assert chunks[0].quantity == 100
        assert chunks[1].quantity == 100
        assert chunks[2].quantity == 100
        assert chunks[3].quantity == 50
        total_qty = sum(c.quantity for c in chunks)
        assert total_qty == 350

    def test_get_execution_policy_factory(self):
        """Test policy factory function."""
        immediate = get_execution_policy(ExecutionPolicyType.IMMEDIATE)
        assert isinstance(immediate, ImmediatePolicy)

        twap = get_execution_policy(ExecutionPolicyType.TWAP, num_chunks=10)
        assert isinstance(twap, TWAPPolicy)
        assert twap.num_chunks == 10

        iceberg = get_execution_policy(ExecutionPolicyType.ICEBERG, visible_quantity=50)
        assert isinstance(iceberg, IcebergPolicy)
        assert iceberg.visible_quantity == 50


class TestExecutionHandler:
    """Tests for the ExecutionHandler."""

    def test_submit_order_simple(self):
        """Test submitting a simple order."""
        handler = ExecutionHandler()
        order, fills = handler.submit_order(
            symbol=Symbol.AAPL,
            direction=Direction.BUY,
            order_type=OrderType.LIMIT,
            quantity=100,
            price=150.0,
            strategy_id="test_strategy",
        )

        assert order.symbol == Symbol.AAPL
        assert order.quantity == 100
        assert order.status == OrderStatus.FILLED  # Simulated external fill
        assert len(fills) >= 1

    def test_internal_matching(self):
        """Test that opposite orders from different strategies match internally."""
        handler = ExecutionHandler()

        # Submit sell order (won't match, goes to book then external)
        sell_order, sell_fills = handler.submit_order(
            symbol=Symbol.AAPL,
            direction=Direction.SELL,
            order_type=OrderType.LIMIT,
            quantity=100,
            price=150.0,
            strategy_id="strategy_a",
        )

        # For this test, we need to prevent external execution to test internal matching
        # Let's create a new handler and add order to book without external execution
        handler2 = ExecutionHandler()
        book = handler2.get_order_book(Symbol.AAPL)

        # Manually add a sell order to the book
        manual_sell = Order(
            symbol=Symbol.AAPL,
            direction=Direction.SELL,
            order_type=OrderType.LIMIT,
            quantity=100,
            remaining_quantity=100,
            price=150.0,
            strategy_id="strategy_a",
        )
        book.add_order(manual_sell)

        # Now submit matching buy order
        buy_order, buy_fills = handler2.submit_order(
            symbol=Symbol.AAPL,
            direction=Direction.BUY,
            order_type=OrderType.LIMIT,
            quantity=100,
            price=150.0,
            strategy_id="strategy_b",
        )

        # Should have matched internally
        assert manual_sell.status == OrderStatus.FILLED
        assert buy_order.status == OrderStatus.FILLED
        # Fills should include the internal match
        assert len(buy_fills) >= 2  # At least the match fills

    def test_order_chunking_with_twap(self):
        """Test order chunking with TWAP policy."""
        handler = ExecutionHandler()
        order, fills = handler.submit_order(
            symbol=Symbol.AAPL,
            direction=Direction.BUY,
            order_type=OrderType.LIMIT,
            quantity=1000,
            price=150.0,
            strategy_id="test_strategy",
            policy=ExecutionPolicyType.TWAP,
            policy_kwargs={"num_chunks": 5},
        )

        # Order should be completely filled via external execution
        assert order.status == OrderStatus.FILLED
        assert order.remaining_quantity == 0
        # Should have fills for each chunk
        assert len(fills) >= 5

    def test_cancel_order(self):
        """Test order cancellation."""
        handler = ExecutionHandler()

        # Create and add an order to book without external execution
        book = handler.get_order_book(Symbol.AAPL)
        order = Order(
            symbol=Symbol.AAPL,
            direction=Direction.BUY,
            order_type=OrderType.LIMIT,
            quantity=100,
            remaining_quantity=100,
            price=150.0,
            strategy_id="test",
        )
        handler._orders[order.order_id] = order
        book.add_order(order)

        # Cancel it
        result = handler.cancel_order(order.order_id)

        assert result is True
        assert order.status == OrderStatus.CANCELLED

    def test_get_pending_orders(self):
        """Test getting pending orders filtered by strategy."""
        handler = ExecutionHandler()

        # Add some orders to the internal tracking
        order1 = Order(
            symbol=Symbol.AAPL,
            direction=Direction.BUY,
            order_type=OrderType.LIMIT,
            quantity=100,
            remaining_quantity=50,
            price=150.0,
            strategy_id="strategy_a",
            status=OrderStatus.PARTIALLY_FILLED,
        )
        order2 = Order(
            symbol=Symbol.TSLA,
            direction=Direction.SELL,
            order_type=OrderType.LIMIT,
            quantity=50,
            remaining_quantity=50,
            price=250.0,
            strategy_id="strategy_b",
            status=OrderStatus.OPEN,
        )
        handler._orders[order1.order_id] = order1
        handler._orders[order2.order_id] = order2

        # Get all pending
        all_pending = handler.get_pending_orders()
        assert len(all_pending) == 2

        # Get filtered
        strategy_a_pending = handler.get_pending_orders(strategy_id="strategy_a")
        assert len(strategy_a_pending) == 1
        assert strategy_a_pending[0].strategy_id == "strategy_a"

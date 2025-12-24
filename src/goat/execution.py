"""
Execution module for order handling and matching.

This module provides:
- Order: Enhanced order model with execution tracking
- OrderBook: Lightweight price-time priority matching engine
- ExecutionPolicy: Strategy pattern for order chunking
- ExecutionHandler: Main orchestrator for order execution
"""

from __future__ import annotations

import uuid
from abc import ABC, abstractmethod
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone

from pydantic import AwareDatetime, BaseModel, Field

from goat.enums import Direction, ExecutionPolicyType, OrderStatus, OrderType, Symbol

# =============================================================================
# Order Model
# =============================================================================


class Order(BaseModel):
    """
    Enhanced order model with execution tracking.

    Extends the concept of OrderEvent with lifecycle management,
    partial fill tracking, and strategy attribution.
    """

    order_id: uuid.UUID = Field(default_factory=uuid.uuid4)
    strategy_id: str = Field(default="default")  # StrategyID
    symbol: Symbol
    direction: Direction
    order_type: OrderType
    quantity: int = Field(..., gt=0, description="Original order quantity")
    remaining_quantity: int = Field(..., gt=0, description="Unfilled quantity")
    price: float = Field(..., ge=0, description="Limit price (0 for market orders)")
    status: OrderStatus = OrderStatus.PENDING
    created_at: AwareDatetime = Field(default_factory=lambda: datetime.now(tz=timezone.utc))
    fills: list[Fill] = Field(default_factory=list)

    def model_post_init(self, __context) -> None:
        """Initialize remaining_quantity to quantity if not set."""
        if self.remaining_quantity > self.quantity:
            self.remaining_quantity = self.quantity

    def apply_fill(self, fill_quantity: int, fill_price: float) -> Fill:
        """Apply a fill to this order and return the Fill record."""
        if fill_quantity > self.remaining_quantity:
            raise ValueError(f"Fill quantity {fill_quantity} exceeds remaining {self.remaining_quantity}")

        fill = Fill(
            order_id=self.order_id,
            quantity=fill_quantity,
            price=fill_price,
            timestamp=datetime.now(tz=timezone.utc),
        )
        self.fills.append(fill)
        self.remaining_quantity -= fill_quantity

        if self.remaining_quantity == 0:
            self.status = OrderStatus.FILLED
        else:
            self.status = OrderStatus.PARTIALLY_FILLED

        return fill

    @property
    def is_complete(self) -> bool:
        """Check if order is fully filled or cancelled."""
        return self.status in (OrderStatus.FILLED, OrderStatus.CANCELLED)

    @property
    def filled_quantity(self) -> int:
        """Total filled quantity."""
        return self.quantity - self.remaining_quantity

    @property
    def average_fill_price(self) -> float | None:
        """Volume-weighted average fill price."""
        if not self.fills:
            return None
        total_value = sum(f.quantity * f.price for f in self.fills)
        total_qty = sum(f.quantity for f in self.fills)
        return total_value / total_qty if total_qty > 0 else None


class Fill(BaseModel):
    """Record of a partial or full order fill."""

    fill_id: uuid.UUID = Field(default_factory=uuid.uuid4)
    order_id: uuid.UUID
    quantity: int = Field(..., gt=0)
    price: float = Field(..., ge=0)
    timestamp: AwareDatetime = Field(default_factory=lambda: datetime.now(tz=timezone.utc))
    commission: float = Field(default=0.0)


# =============================================================================
# Order Book (Matching Engine)
# =============================================================================


@dataclass
class OrderBookEntry:
    """Entry in the order book with price-time priority."""

    order: Order
    timestamp: datetime = field(default_factory=lambda: datetime.now(tz=timezone.utc))


class OrderBook:
    """
    Lightweight price-time priority matching engine for a single symbol.

    Maintains separate bid (buy) and ask (sell) queues. When a new order
    arrives, attempts to match against the opposite side.

    Matching Logic:
    - Bids sorted by price descending (highest first), then time ascending
    - Asks sorted by price ascending (lowest first), then time ascending
    - Orders match when bid price >= ask price
    - Match price is the resting order's price (price improvement for aggressor)
    """

    def __init__(self, symbol: Symbol):
        self.symbol = symbol
        self._bids: list[OrderBookEntry] = []  # Buy orders
        self._asks: list[OrderBookEntry] = []  # Sell orders
        self._orders: dict[uuid.UUID, Order] = {}

    def add_order(self, order: Order) -> list[Fill]:
        """
        Add an order to the book and attempt matching.

        Returns list of fills generated from matching.
        """
        if order.symbol != self.symbol:
            raise ValueError(f"Order symbol {order.symbol} doesn't match book symbol {self.symbol}")

        order.status = OrderStatus.OPEN
        self._orders[order.order_id] = order

        # Attempt matching
        fills = self._match_order(order)

        # If order still has remaining quantity, add to book
        if not order.is_complete and order.remaining_quantity > 0:
            entry = OrderBookEntry(order=order)
            if order.direction == Direction.BUY:
                self._bids.append(entry)
                self._sort_bids()
            else:
                self._asks.append(entry)
                self._sort_asks()

        return fills

    def cancel_order(self, order_id: uuid.UUID) -> bool:
        """Cancel an order if it exists and is still open."""
        order = self._orders.get(order_id)
        if order is None or order.is_complete:
            return False

        order.status = OrderStatus.CANCELLED

        # Remove from book
        self._bids = [e for e in self._bids if e.order.order_id != order_id]
        self._asks = [e for e in self._asks if e.order.order_id != order_id]

        return True

    def get_order(self, order_id: uuid.UUID) -> Order | None:
        """Get an order by ID."""
        return self._orders.get(order_id)

    def _match_order(self, incoming: Order) -> list[Fill]:
        """Match incoming order against resting orders."""
        fills: list[Fill] = []

        if incoming.direction == Direction.BUY:
            # Match against asks (sells)
            fills = self._match_against_side(incoming, self._asks, is_buy=True)
        else:
            # Match against bids (buys)
            fills = self._match_against_side(incoming, self._bids, is_buy=False)

        return fills

    def _match_against_side(self, incoming: Order, opposite_side: list[OrderBookEntry], is_buy: bool) -> list[Fill]:
        """Match incoming order against the opposite side of the book."""
        fills: list[Fill] = []
        entries_to_remove: list[OrderBookEntry] = []

        for entry in opposite_side:
            if incoming.remaining_quantity <= 0:
                break

            resting = entry.order
            if resting.remaining_quantity <= 0:
                entries_to_remove.append(entry)
                continue

            # Check price compatibility
            if is_buy:
                # Buy order matches if incoming price >= resting ask price
                if incoming.order_type == OrderType.LIMIT and incoming.price < resting.price:
                    break  # No more matches possible (asks sorted ascending)
            else:
                # Sell order matches if incoming price <= resting bid price
                if incoming.order_type == OrderType.LIMIT and incoming.price > resting.price:
                    break  # No more matches possible (bids sorted descending)

            # Execute match at resting order's price
            match_qty = min(incoming.remaining_quantity, resting.remaining_quantity)
            match_price = resting.price

            # Create fills for both sides
            incoming_fill = incoming.apply_fill(match_qty, match_price)
            resting_fill = resting.apply_fill(match_qty, match_price)
            fills.extend([incoming_fill, resting_fill])

            if resting.is_complete:
                entries_to_remove.append(entry)

        # Remove fully filled entries
        for entry in entries_to_remove:
            if entry in opposite_side:
                opposite_side.remove(entry)

        return fills

    def _sort_bids(self) -> None:
        """Sort bids by price descending, then time ascending."""
        self._bids.sort(key=lambda e: (-e.order.price, e.timestamp))

    def _sort_asks(self) -> None:
        """Sort asks by price ascending, then time ascending."""
        self._asks.sort(key=lambda e: (e.order.price, e.timestamp))

    @property
    def best_bid(self) -> float | None:
        """Best (highest) bid price."""
        return self._bids[0].order.price if self._bids else None

    @property
    def best_ask(self) -> float | None:
        """Best (lowest) ask price."""
        return self._asks[0].order.price if self._asks else None

    @property
    def spread(self) -> float | None:
        """Current bid-ask spread."""
        if self.best_bid is not None and self.best_ask is not None:
            return self.best_ask - self.best_bid
        return None


# =============================================================================
# Execution Policies
# =============================================================================


class BaseExecutionPolicy(ABC):
    """
    Base class for execution policies.

    Execution policies determine how orders are split/chunked
    for execution. This enables strategies like TWAP, VWAP, Iceberg, etc.
    """

    @abstractmethod
    def split_order(self, order: Order) -> list[Order]:
        """
        Split an order into chunks based on the policy.

        Returns a list of child orders that sum to the original quantity.
        """
        raise NotImplementedError("Subclasses must implement this method")


class ImmediatePolicy(BaseExecutionPolicy):
    """Execute entire order at once (no splitting)."""

    def split_order(self, order: Order) -> list[Order]:
        """Return the order as-is."""
        return [order]


class TWAPPolicy(BaseExecutionPolicy):
    """
    Time-Weighted Average Price policy.

    Splits large orders into equal-sized chunks to be executed
    over a time period to minimize market impact.
    """

    def __init__(self, num_chunks: int = 5, interval_seconds: float = 60.0):
        if num_chunks < 1:
            raise ValueError("num_chunks must be at least 1")
        self.num_chunks = num_chunks
        self.interval_seconds = interval_seconds

    def split_order(self, order: Order) -> list[Order]:
        """Split order into equal-sized chunks."""
        if order.remaining_quantity <= self.num_chunks:
            # Don't split if quantity is too small
            return [order]

        chunk_size = order.remaining_quantity // self.num_chunks
        remainder = order.remaining_quantity % self.num_chunks

        chunks: list[Order] = []
        for i in range(self.num_chunks):
            qty = chunk_size + (1 if i < remainder else 0)
            if qty > 0:
                chunk = Order(
                    strategy_id=order.strategy_id,
                    symbol=order.symbol,
                    direction=order.direction,
                    order_type=order.order_type,
                    quantity=qty,
                    remaining_quantity=qty,
                    price=order.price,
                )
                chunks.append(chunk)

        return chunks


class IcebergPolicy(BaseExecutionPolicy):
    """
    Iceberg order policy.

    Shows only a portion of the total order quantity. As visible
    portions are filled, new visible portions are released.
    """

    def __init__(self, visible_quantity: int = 100):
        if visible_quantity < 1:
            raise ValueError("visible_quantity must be at least 1")
        self.visible_quantity = visible_quantity

    def split_order(self, order: Order) -> list[Order]:
        """Split order into visible-sized chunks."""
        if order.remaining_quantity <= self.visible_quantity:
            return [order]

        chunks: list[Order] = []
        remaining = order.remaining_quantity

        while remaining > 0:
            qty = min(self.visible_quantity, remaining)
            chunk = Order(
                strategy_id=order.strategy_id,
                symbol=order.symbol,
                direction=order.direction,
                order_type=order.order_type,
                quantity=qty,
                remaining_quantity=qty,
                price=order.price,
            )
            chunks.append(chunk)
            remaining -= qty

        return chunks


def get_execution_policy(policy_type: ExecutionPolicyType, **kwargs) -> BaseExecutionPolicy:
    """Factory function to create execution policies."""
    policies = {
        ExecutionPolicyType.IMMEDIATE: ImmediatePolicy,
        ExecutionPolicyType.TWAP: TWAPPolicy,
        ExecutionPolicyType.ICEBERG: IcebergPolicy,
    }
    policy_class = policies.get(policy_type)
    if policy_class is None:
        raise ValueError(f"Unknown policy type: {policy_type}")
    return policy_class(**kwargs)


# =============================================================================
# Execution Handler
# =============================================================================


class ExecutionHandler:
    """
    Orchestrates order execution across strategies.

    Flow:
    1. Receive order from strategy
    2. Apply execution policy (chunk if needed)
    3. Attempt internal matching via OrderBook
    4. Route unmatched orders to external execution (simulated)
    5. Return fills for all executions
    """

    def __init__(self, default_policy: ExecutionPolicyType = ExecutionPolicyType.IMMEDIATE):
        self._default_policy = default_policy
        self._order_books: dict[Symbol, OrderBook] = defaultdict(lambda: None)  # type: ignore
        self._orders: dict[uuid.UUID, Order] = {}
        self._parent_child_map: dict[uuid.UUID, list[uuid.UUID]] = {}  # parent -> children

    def submit_order(
        self,
        symbol: Symbol,
        direction: Direction,
        order_type: OrderType,
        quantity: int,
        price: float,
        strategy_id: str = "default",
        policy: ExecutionPolicyType | None = None,
        policy_kwargs: dict | None = None,
    ) -> tuple[Order, list[Fill]]:
        """
        Submit an order for execution.

        Args:
            symbol: Trading symbol
            direction: BUY or SELL
            order_type: LIMIT or MARKET
            quantity: Order quantity
            price: Limit price (ignored for market orders)
            strategy_id: ID of the strategy submitting the order
            policy: Execution policy (defaults to handler's default)
            policy_kwargs: Additional kwargs for policy construction

        Returns:
            Tuple of (parent order, list of all fills)
        """
        # Create parent order
        parent_order = Order(
            strategy_id=strategy_id,
            symbol=symbol,
            direction=direction,
            order_type=order_type,
            quantity=quantity,
            remaining_quantity=quantity,
            price=price,
        )
        self._orders[parent_order.order_id] = parent_order

        # Apply execution policy
        policy_type = policy or self._default_policy
        policy_kwargs = policy_kwargs or {}
        exec_policy = get_execution_policy(policy_type, **policy_kwargs)
        child_orders = exec_policy.split_order(parent_order)

        # Track parent-child relationship
        if len(child_orders) > 1 or child_orders[0].order_id != parent_order.order_id:
            self._parent_child_map[parent_order.order_id] = [c.order_id for c in child_orders]
            for child in child_orders:
                self._orders[child.order_id] = child

        # Execute each chunk
        all_fills: list[Fill] = []
        for child in child_orders:
            fills = self._execute_order(child)
            all_fills.extend(fills)

            # Update parent order status based on child fills
            for fill in fills:
                if fill.order_id == child.order_id:
                    # This fill is for our child order
                    parent_order.remaining_quantity -= fill.quantity
                    if parent_order.remaining_quantity <= 0:
                        parent_order.status = OrderStatus.FILLED
                    elif parent_order.remaining_quantity < parent_order.quantity:
                        parent_order.status = OrderStatus.PARTIALLY_FILLED

        return parent_order, all_fills

    def cancel_order(self, order_id: uuid.UUID) -> bool:
        """Cancel an order and all its children."""
        order = self._orders.get(order_id)
        if order is None:
            return False

        # Cancel children if any
        child_ids = self._parent_child_map.get(order_id, [])
        for child_id in child_ids:
            child = self._orders.get(child_id)
            if child and not child.is_complete:
                book = self._get_order_book(child.symbol)
                book.cancel_order(child_id)

        # Cancel parent
        if not order.is_complete:
            order.status = OrderStatus.CANCELLED

        return True

    def get_order(self, order_id: uuid.UUID) -> Order | None:
        """Get an order by ID."""
        return self._orders.get(order_id)

    def get_pending_orders(self, strategy_id: str | None = None) -> list[Order]:
        """Get all pending orders, optionally filtered by strategy."""
        pending = [o for o in self._orders.values() if not o.is_complete]
        if strategy_id is not None:
            pending = [o for o in pending if o.strategy_id == strategy_id]
        return pending

    def get_order_book(self, symbol: Symbol) -> OrderBook:
        """Get the order book for a symbol."""
        return self._get_order_book(symbol)

    def _get_order_book(self, symbol: Symbol) -> OrderBook:
        """Get or create order book for symbol."""
        if self._order_books.get(symbol) is None:
            self._order_books[symbol] = OrderBook(symbol)
        return self._order_books[symbol]

    def _execute_order(self, order: Order) -> list[Fill]:
        """
        Execute a single order.

        First attempts internal matching, then simulates external execution.
        """
        fills: list[Fill] = []

        # Step 1: Internal matching via order book
        book = self._get_order_book(order.symbol)
        internal_fills = book.add_order(order)
        fills.extend(internal_fills)

        # Step 2: External execution for remaining quantity
        if not order.is_complete and order.remaining_quantity > 0:
            external_fills = self._execute_externally(order)
            fills.extend(external_fills)

        return fills

    def _execute_externally(self, order: Order) -> list[Fill]:
        """
        Simulate external order execution.

        In a real system, this would route to a broker API.
        For now, we simulate immediate fill at the order price.
        """
        if order.remaining_quantity <= 0:
            return []

        # Simulate fill at order price (or slightly worse for realism)
        slippage = 0.0001 if order.order_type == OrderType.MARKET else 0.0
        fill_price = order.price * (1 + slippage if order.direction == Direction.BUY else 1 - slippage)

        fill = order.apply_fill(order.remaining_quantity, fill_price)
        return [fill]

"""Portfolio module for position management and event orchestration.

The Portfolio is the central coordinator that:
- Manages positions and cash
- Maintains an event queue
- Routes events to appropriate handlers
- Converts signals to orders
"""

from collections import deque
from datetime import datetime, timezone

from goat.data_handler import Candle, CandleDataHandler
from goat.enums import Action, Direction, OrderType, Symbol
from goat.event import FillEvent, MarketEvent, SignalEvent
from goat.execution import ExecutionHandler
from goat.strategy import Strategy


class Portfolio:
    """Manages positions, strategies, and event flow.

    The Portfolio coordinates the event-driven trading loop:
    1. Receives MarketEvents from DataHandler
    2. Feeds candles to Strategies
    3. Receives SignalEvents from Strategies
    4. Generates OrderEvents for ExecutionHandler
    5. Processes FillEvents to update positions

    Attributes:
        cash: Current cash balance.
        total_value: Total portfolio value (cash + positions).
        positions: Map of symbol to quantity held.
        data_handler: Data provider for market data.
        execution_handler: Handler for order execution.
        active_strategies: List of running strategies.
        event_queue: Queue of events to process.
        default_order_quantity: Default quantity for orders.
    """

    def __init__(
        self,
        cash: float,
        data_handler: CandleDataHandler,
        execution_handler: ExecutionHandler,
        default_order_quantity: int = 10,
    ) -> None:
        """Initialize portfolio.

        Args:
            cash: Starting cash balance.
            data_handler: Data provider for market data.
            execution_handler: Handler for order execution.
            default_order_quantity: Default quantity for orders.
        """
        self.cash = cash
        self.total_value = cash
        self.positions: dict[Symbol, int] = {}
        self._latest_prices: dict[Symbol, float] = {}  # Track latest price per symbol
        self.data_handler = data_handler
        self.execution_handler = execution_handler
        self.active_strategies = []
        self.event_queue = deque()
        self.default_order_quantity = default_order_quantity
        self._running = False

    def start(self) -> None:
        """Start the portfolio and run the main loop."""
        self._running = True
        self._run_event_loop()

    def stop(self) -> None:
        """Stop all active strategies."""
        for strategy in self.active_strategies:
            strategy.stop()
        self._running = False

    def add_strategy(self, strategy: Strategy) -> None:
        """Add and start a strategy.

        Args:
            strategy: Strategy to add.
        """
        # Wire the strategy's signal callback to our handler
        strategy.on_signal = self._on_strategy_signal
        strategy.run()
        self.active_strategies.append(strategy)

    def remove_strategy(self, strategy: Strategy) -> None:
        """Remove and stop a strategy.

        Args:
            strategy: Strategy to remove.
        """
        if strategy not in self.active_strategies:
            return
        strategy.stop()
        self.active_strategies.remove(strategy)

    def remove_strategies_by_id(self, strategy_id: str) -> None:
        """Remove all strategies with the given ID.

        Args:
            strategy_id: ID of strategies to remove.
        """
        strategies_to_keep: list[Strategy] = []
        strategies_to_stop: list[Strategy] = []
        for strategy in self.active_strategies:
            if strategy.id == strategy_id:
                strategies_to_stop.append(strategy)
            else:
                strategies_to_keep.append(strategy)
        for strategy in strategies_to_stop:
            strategy.stop()
        self.active_strategies = strategies_to_keep

    # =========================================================================
    # Event Processing
    # =========================================================================

    def _run_event_loop(self) -> None:
        """Main event loop: fetch data and process events."""
        while self._running:
            # Get next candle from data handler
            candle = self.data_handler.next_candle()
            if candle is None:
                break

            # Emit market event
            self.event_queue.append(MarketEvent())

            # Process all events
            self._process_events(candle)

    def _process_events(self, current_candle: Candle) -> None:
        """Process all events in the queue.

        Args:
            current_candle: Current candle for price reference.
        """
        while self.event_queue:
            event = self.event_queue.popleft()

            if isinstance(event, MarketEvent):
                self._on_market(event, current_candle)
            elif isinstance(event, SignalEvent):
                self._on_signal(event, current_candle)
            elif isinstance(event, FillEvent):
                self._on_fill(event)

    def _on_market(self, event: MarketEvent, candle: Candle) -> None:
        """Handle market event by feeding candle to strategies.

        Args:
            event: The market event.
            candle: Current candle data.
        """
        for strategy in self.active_strategies:
            action = strategy.calculate_signal(candle)
            if action is not None:
                signal = SignalEvent(
                    strategy_id=strategy.id,
                    symbol=strategy.symbol,
                    action=action,
                    datetime=datetime.now(tz=timezone.utc),
                )
                self.event_queue.append(signal)

    def _on_signal(self, event: SignalEvent, candle: Candle) -> None:
        """Handle signal event by generating orders.

        Args:
            event: The signal event.
            candle: Current candle for price reference.
        """
        # Determine order direction
        direction = Direction.BUY if event.action == Action.BUY else Direction.SELL

        # Check if we should trade (simple logic: don't short, don't over-buy)
        current_position = self.positions.get(event.symbol, 0)
        if direction == Direction.SELL and current_position <= 0:
            return  # Skip: no position to sell

        # Submit order through execution handler
        order, fills = self.execution_handler.submit_order(
            symbol=event.symbol,
            direction=direction,
            order_type=OrderType.MARKET,
            quantity=min(self.default_order_quantity, current_position)
            if direction == Direction.SELL
            else self.default_order_quantity,
            price=candle.close,
            strategy_id=event.strategy_id,
        )

        # Queue fill events for position updates
        for fill in fills:
            fill_event = FillEvent(
                fill_type="FULL" if order.is_complete else "PARTIAL",
                order_id=fill.order_id,
                quantity=fill.quantity,
                price=fill.price,
                datetime=fill.timestamp,
                fill_cost=fill.quantity * fill.price,
                commission=fill.commission,
            )
            self.event_queue.append(fill_event)

    def _on_fill(self, event: FillEvent) -> None:
        """Handle fill event by updating positions and cash.

        Args:
            event: The fill event.
        """
        # We need to look up the order to determine direction
        order = self.execution_handler.get_order(event.order_id)
        if order is None:
            return

        symbol = order.symbol

        if order.direction == Direction.BUY:
            self.positions[symbol] = self.positions.get(symbol, 0) + event.quantity
            self.cash -= event.fill_cost + event.commission
        else:  # SELL
            self.positions[symbol] = self.positions.get(symbol, 0) - event.quantity
            self.cash += event.fill_cost - event.commission

        # Update latest price for this symbol and recalculate total value
        self._latest_prices[symbol] = event.price
        self._update_total_value()

    def _on_strategy_signal(self, signal: object) -> None:
        """Callback for strategies to emit signals directly.

        Args:
            signal: SignalEvent from strategy.
        """
        if isinstance(signal, SignalEvent):
            self.event_queue.append(signal)

    def _update_total_value(self) -> None:
        """Update total portfolio value using latest known prices per symbol."""
        position_value = sum(qty * self._latest_prices.get(symbol, 0.0) for symbol, qty in self.positions.items())
        self.total_value = self.cash + position_value

    # =========================================================================
    # Query Methods
    # =========================================================================

    def get_position(self, symbol: Symbol) -> int:
        """Get current position for a symbol.

        Args:
            symbol: The symbol to query.

        Returns:
            Current position quantity (0 if no position).
        """
        return self.positions.get(symbol, 0)

    def get_unrealized_pnl(self, symbol: Symbol, current_price: float) -> float:
        """Calculate unrealized P&L for a position.

        Args:
            symbol: The symbol to query.
            current_price: Current market price.

        Returns:
            Unrealized profit/loss (simplified calculation).
        """
        position = self.positions.get(symbol, 0)
        if position == 0:
            return 0.0
        # Note: This requires tracking entry price, which we don't currently do
        # For now, return 0 as placeholder
        return 0.0

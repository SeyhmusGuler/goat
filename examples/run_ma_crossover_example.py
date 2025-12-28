#!/usr/bin/env python3
"""
Complete Moving Average Crossover Trading Example
==================================================

This example demonstrates the full GOAT trading pipeline:
1. Generate synthetic AAPL price data
2. Run a Moving Average Crossover strategy
3. Visualize candles, moving averages, signals, and performance

Run with: uv run python examples/run_ma_crossover_example.py
"""

import random
from datetime import datetime, timezone

import polars as pl

from goat.data_handler import HistoricDataHandler
from goat.enums import Action, Symbol
from goat.execution import ExecutionHandler
from goat.strategy import MovingAverageCrossStrategy

# =============================================================================
# ANSI Color Codes for Visual Output
# =============================================================================


class Colors:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"

    # Signal colors
    GREEN = "\033[92m"  # BUY
    RED = "\033[91m"  # SELL
    YELLOW = "\033[93m"  # Warning/Info
    CYAN = "\033[96m"  # Data
    BLUE = "\033[94m"  # Headers
    MAGENTA = "\033[95m"  # Performance


# =============================================================================
# Synthetic Data Generation
# =============================================================================


def generate_price_data(
    symbol: str = "AAPL",
    start_price: float = 150.0,
    num_candles: int = 100,
    seed: int = 42,
) -> pl.DataFrame:
    """
    Generate synthetic OHLCV data with realistic price movements.

    Creates a price series that will generate MA crossovers for demonstration.
    Uses a random walk with trend changes to create interesting patterns.
    """
    random.seed(seed)

    prices = []
    timestamps = []
    volumes = []

    price = start_price
    base_timestamp = int(datetime(2024, 1, 1, 9, 30, tzinfo=timezone.utc).timestamp() * 1_000_000_000)
    period_ns = 60 * 1_000_000_000  # 1 minute candles

    # Create price movements with trend changes
    trend = 0.1  # Initial upward trend

    for i in range(num_candles):
        # Change trend periodically to create crossovers
        if i % 25 == 0:
            trend = -trend  # Reverse trend

        # Random walk with trend
        daily_return = trend + random.gauss(0, 0.5)
        price = max(price * (1 + daily_return / 100), 1.0)  # Ensure positive

        # Generate OHLCV
        volatility = random.uniform(0.3, 0.8)
        open_price = price * (1 + random.uniform(-volatility, volatility) / 100)
        high_price = max(price, open_price) * (1 + random.uniform(0, volatility) / 100)
        low_price = min(price, open_price) * (1 - random.uniform(0, volatility) / 100)
        close_price = price
        volume = int(random.uniform(50000, 200000))

        prices.append(
            {
                "open": round(open_price, 2),
                "high": round(high_price, 2),
                "low": round(low_price, 2),
                "close": round(close_price, 2),
            }
        )
        timestamps.append(base_timestamp + i * period_ns)
        volumes.append(volume)

    return pl.DataFrame(
        {
            "start_timestamp": timestamps,
            "time_period": [period_ns] * num_candles,
            "open": [p["open"] for p in prices],
            "high": [p["high"] for p in prices],
            "low": [p["low"] for p in prices],
            "close": [p["close"] for p in prices],
            "volume": volumes,
            "tick_count": list(range(num_candles)),
        }
    )


# =============================================================================
# Visual Output Functions
# =============================================================================


def print_header():
    """Print the example header."""
    print(f"\n{Colors.BLUE}{'=' * 80}")
    print("  🐐 GOAT - Moving Average Crossover Trading Example")
    print(f"{'=' * 80}{Colors.RESET}\n")


def print_candle_header():
    """Print the candle data table header."""
    print(f"{Colors.BOLD}{Colors.CYAN}")
    print(
        f"{'Tick':>5} │ {'Time':^12} │ {'Close':>8} │ {'Short MA':>9} │ {'Long MA':>9} │ {'Signal':^10} │ {'Position':>8} │ {'Cash':>12}"
    )
    print(f"{'─' * 5}─┼─{'─' * 12}─┼─{'─' * 8}─┼─{'─' * 9}─┼─{'─' * 9}─┼─{'─' * 10}─┼─{'─' * 8}─┼─{'─' * 12}")
    print(Colors.RESET)


def format_signal(action: Action | None) -> str:
    """Format a signal for display."""
    if action is None:
        return f"{Colors.DIM}   ---   {Colors.RESET}"
    elif action == Action.BUY:
        return f"{Colors.GREEN}{Colors.BOLD}  🟢 BUY  {Colors.RESET}"
    else:
        return f"{Colors.RED}{Colors.BOLD}  🔴 SELL {Colors.RESET}"


def print_candle_row(
    tick: int,
    timestamp: int,
    close: float,
    short_ma: float | None,
    long_ma: float | None,
    signal: Action | None,
    position: int,
    cash: float,
):
    """Print a single candle row with visual formatting."""
    time_str = datetime.fromtimestamp(timestamp / 1_000_000_000).strftime("%H:%M:%S")

    short_ma_str = f"{short_ma:9.2f}" if short_ma else "    ---  "
    long_ma_str = f"{long_ma:9.2f}" if long_ma else "    ---  "
    signal_str = format_signal(signal)

    # Color the row based on signal
    row_color = Colors.RESET
    if signal == Action.BUY:
        row_color = Colors.GREEN
    elif signal == Action.SELL:
        row_color = Colors.RED

    print(
        f"{row_color}{tick:5d} │ {time_str:^12} │ {close:8.2f} │ {short_ma_str} │ {long_ma_str} │{Colors.RESET}{signal_str}{row_color}│ {position:8d} │ ${cash:11,.2f}{Colors.RESET}"
    )


def print_performance_summary(
    initial_cash: float,
    final_cash: float,
    final_position: int,
    final_price: float,
    trades: list[dict],
):
    """Print the final performance summary."""
    total_value = final_cash + (final_position * final_price)
    total_return = ((total_value - initial_cash) / initial_cash) * 100

    num_trades = len(trades)
    num_buys = sum(1 for t in trades if t["action"] == "BUY")
    num_sells = sum(1 for t in trades if t["action"] == "SELL")

    print(f"\n{Colors.MAGENTA}{'=' * 80}")
    print("  📊 PERFORMANCE SUMMARY")
    print(f"{'=' * 80}{Colors.RESET}\n")

    print(f"  {Colors.BOLD}Portfolio Value{Colors.RESET}")
    print(f"  ├─ Initial Cash:     ${initial_cash:>12,.2f}")
    print(f"  ├─ Final Cash:       ${final_cash:>12,.2f}")
    print(
        f"  ├─ Position Value:   ${final_position * final_price:>12,.2f} ({final_position} shares @ ${final_price:.2f})"
    )
    print(f"  └─ Total Value:      ${total_value:>12,.2f}")

    return_color = Colors.GREEN if total_return >= 0 else Colors.RED
    print(f"\n  {Colors.BOLD}Returns{Colors.RESET}")
    print(f"  └─ Total Return:     {return_color}{total_return:>+11.2f}%{Colors.RESET}")

    print(f"\n  {Colors.BOLD}Trading Activity{Colors.RESET}")
    print(f"  ├─ Total Trades:     {num_trades:>12}")
    print(f"  ├─ Buy Orders:       {num_buys:>12}")
    print(f"  └─ Sell Orders:      {num_sells:>12}")

    if trades:
        print(f"\n  {Colors.BOLD}Trade Log{Colors.RESET}")
        for i, trade in enumerate(trades[-5:], 1):  # Show last 5 trades
            action_icon = "🟢" if trade["action"] == "BUY" else "🔴"
            print(f"  {action_icon} Tick {trade['tick']:3d}: {trade['action']:4} @ ${trade['price']:.2f}")

    print(f"\n{Colors.MAGENTA}{'=' * 80}{Colors.RESET}\n")


# =============================================================================
# Main Trading Loop (Custom to show visual output)
# =============================================================================


def run_trading_example():
    """
    Run the complete trading pipeline with visual output.

    This is a custom event loop that mimics Portfolio.start() but adds
    rich console output to visualize the trading process.
    """

    print_header()

    # Configuration
    INITIAL_CASH = 100_000.0
    SHORT_WINDOW = 5
    LONG_WINDOW = 20
    ORDER_QUANTITY = 10
    SYMBOL = Symbol.AAPL

    print(f"  {Colors.BOLD}Configuration{Colors.RESET}")
    print(f"  ├─ Symbol:           {SYMBOL}")
    print(f"  ├─ Initial Cash:     ${INITIAL_CASH:,.2f}")
    print(f"  ├─ Short MA Window:  {SHORT_WINDOW}")
    print(f"  ├─ Long MA Window:   {LONG_WINDOW}")
    print(f"  └─ Order Quantity:   {ORDER_QUANTITY} shares\n")

    # Generate synthetic data
    print(f"  {Colors.CYAN}Generating synthetic price data...{Colors.RESET}")
    df = generate_price_data(symbol=str(SYMBOL), num_candles=100)
    print(f"  ✓ Generated {len(df)} candles\n")

    # Setup components
    data_handler = HistoricDataHandler(df=df)
    _ = ExecutionHandler()

    strategy = MovingAverageCrossStrategy(
        short_window=SHORT_WINDOW,
        long_window=LONG_WINDOW,
        symbol=SYMBOL,
    )
    strategy.run()  # Initialize the strategy

    # Portfolio state (manual tracking for visualization)
    cash = INITIAL_CASH
    position = 0
    trades: list[dict] = []

    print_candle_header()

    # Main event loop
    tick = 0
    final_price = 0.0

    while True:
        candle = data_handler.next_candle()
        if candle is None:
            break

        tick += 1
        final_price = candle.close

        # Calculate signal
        signal = strategy.calculate_signal(candle)

        # Get MA values (access internal state for visualization)
        short_ma = strategy._prev_short_ma
        long_ma = strategy._prev_long_ma

        # Execute trades
        if signal is not None:
            if signal == Action.BUY and cash >= candle.close * ORDER_QUANTITY:
                # Execute buy
                cost = candle.close * ORDER_QUANTITY
                cash -= cost
                position += ORDER_QUANTITY
                trades.append(
                    {
                        "tick": tick,
                        "action": "BUY",
                        "price": candle.close,
                        "quantity": ORDER_QUANTITY,
                    }
                )
            elif signal == Action.SELL and position >= ORDER_QUANTITY:
                # Execute sell
                revenue = candle.close * ORDER_QUANTITY
                cash += revenue
                position -= ORDER_QUANTITY
                trades.append(
                    {
                        "tick": tick,
                        "action": "SELL",
                        "price": candle.close,
                        "quantity": ORDER_QUANTITY,
                    }
                )
            else:
                signal = None  # Can't execute, clear signal

        # Print the row
        print_candle_row(
            tick=tick,
            timestamp=candle.start_timestamp,
            close=candle.close,
            short_ma=short_ma,
            long_ma=long_ma,
            signal=signal,
            position=position,
            cash=cash,
        )

    strategy.stop()

    # Print summary
    print_performance_summary(
        initial_cash=INITIAL_CASH,
        final_cash=cash,
        final_position=position,
        final_price=final_price,
        trades=trades,
    )


if __name__ == "__main__":
    run_trading_example()

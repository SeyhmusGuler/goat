from enum import StrEnum


class Symbol(StrEnum):
    AAPL = "AAPL"
    TSLA = "TSLA"


class Action(StrEnum):
    BUY = "buy"
    SELL = "sell"


class Direction(StrEnum):
    BUY = "buy"
    SELL = "sell"


class OrderType(StrEnum):
    LIMIT = "limit"
    MARKET = "market"


class OrderStatus(StrEnum):
    PENDING = "pending"  # Awaiting processing
    OPEN = "open"  # In order book, awaiting match
    PARTIALLY_FILLED = "partially_filled"
    FILLED = "filled"
    CANCELLED = "cancelled"


class ExecutionPolicyType(StrEnum):
    IMMEDIATE = "immediate"  # Execute entire order at once
    TWAP = "twap"  # Time-weighted average price chunks
    ICEBERG = "iceberg"  # Hidden quantity with visible portion

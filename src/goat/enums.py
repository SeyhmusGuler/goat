from __future__ import annotations

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

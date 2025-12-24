# GOAT Architecture Documentation

> **G**uler's **O**p **A**lgo **T**rading - Event-Driven Algorithmic Trading Bot

This document describes the architecture of the GOAT trading system, including component interactions, event flow, and usage patterns.

---

## Table of Contents

1. [System Overview](#system-overview)
2. [Event-Driven Architecture](#event-driven-architecture)
3. [Core Modules](#core-modules)
   - [Events](#events)
   - [Data Handler](#data-handler)
   - [Strategy](#strategy)
   - [Portfolio](#portfolio)
   - [Execution](#execution)
4. [Component Interactions](#component-interactions)
5. [Usage Example](#usage-example)

---

## System Overview

GOAT is an event-driven backtesting and trading framework. The system processes market data through a pipeline of components, each communicating via strongly-typed events.

```mermaid
flowchart TB
    subgraph DataLayer["Data Layer"]
        DH[DataHandler]
        HD[(Historic Data)]
        SD[(Stream Data)]
    end
    
    subgraph CoreEngine["Core Engine"]
        P[Portfolio]
        EQ[("Event Queue")]
    end
    
    subgraph Strategies["Strategies"]
        S1[Strategy 1]
        S2[Strategy 2]
        SN[Strategy N]
    end
    
    subgraph Execution["Execution Layer"]
        EH[ExecutionHandler]
        OB[OrderBook]
        EP[ExecutionPolicy]
    end
    
    HD --> DH
    SD --> DH
    DH -->|MarketEvent| EQ
    EQ --> P
    P -->|candle| S1 & S2 & SN
    S1 & S2 & SN -->|SignalEvent| EQ
    P -->|submit_order| EH
    EH --> OB
    EH --> EP
    EH -->|FillEvent| EQ
    EQ --> P
```

---

## Event-Driven Architecture

The system is built around four event types that flow through a central event queue:

```mermaid
sequenceDiagram
    participant DH as DataHandler
    participant EQ as EventQueue
    participant P as Portfolio
    participant S as Strategy
    participant EH as ExecutionHandler
    
    DH->>EQ: MarketEvent (new candle)
    EQ->>P: process MarketEvent
    P->>S: calculate_signal(candle)
    S->>EQ: SignalEvent (BUY/SELL)
    EQ->>P: process SignalEvent
    P->>EH: submit_order(symbol, direction, qty, price)
    EH->>EH: match internally (OrderBook)
    EH->>EH: execute externally
    EH-->>P: returns (Order, list[Fill])
    P->>EQ: FillEvent (from fills)
    EQ->>P: process FillEvent
    P->>P: update positions
```

### Event Types

| Event | Trigger | Contains | Consumer |
|-------|---------|----------|----------|
| `MarketEvent` | New candle available | (minimal) | Portfolio → Strategy |
| `SignalEvent` | Strategy generates signal | symbol, action, strategy_id | Portfolio |
| `FillEvent` | Order executed | order_id, quantity, price, commission | Portfolio |

> **Note:** `OrderEvent` exists in the codebase but is not currently used in the event flow. 
> Portfolio directly calls `ExecutionHandler.submit_order()` instead of creating OrderEvents.

---

## Core Modules

### Events

**File:** `src/goat/event.py`

Defines the event hierarchy using Pydantic models for validation and serialization.

```mermaid
classDiagram
    class Event {
        +event_type: Literal
    }
    class MarketEvent {
        +event_type = "MARKET"
    }
    class SignalEvent {
        +event_type = "SIGNAL"
        +strategy_id: StrategyID
        +symbol: Symbol
        +action: Action
        +datetime: AwareDatetime
    }
    class OrderEvent {
        +event_type = "ORDER"
        +order_id: UUID
        +symbol: Symbol
        +direction: Direction
        +order_type: OrderType
        +quantity: int
        +price: float
    }
    class FillEvent {
        +event_type = "FILL"
        +fill_type: Literal["PARTIAL", "FULL"]
        +order_id: UUID
        +quantity: int
        +price: float
        +datetime: AwareDatetime
        +fill_cost: float
        +commission: float
    }
    
    Event <|-- MarketEvent
    Event <|-- SignalEvent
    Event <|-- OrderEvent
    Event <|-- FillEvent
```

---

### Data Handler

**File:** `src/goat/data_handler.py`

Provides market data through a protocol-based abstraction.

```mermaid
classDiagram
    class CandleDataHandler {
        <<Protocol>>
        +next_candle() Candle | None
    }
    class HistoricDataHandler {
        +df: DataFrame
        +next_candle_index: int
        +next_candle() Candle | None
    }
    class StreamDataHandler {
        +data_stream: Iterator[Candle]
        +next_candle() Candle | None
    }
    class Candle {
        +start_timestamp: int
        +time_period: int
        +open: float
        +high: float
        +low: float
        +close: float
        +volume: int
        +tick_count: int
    }
    
    CandleDataHandler <|.. HistoricDataHandler
    CandleDataHandler <|.. StreamDataHandler
    HistoricDataHandler --> Candle
    StreamDataHandler --> Candle
```

**Usage:**
- `HistoricDataHandler`: For backtesting with historical DataFrame
- `StreamDataHandler`: For live trading with streaming data

---

### Strategy

**File:** `src/goat/strategy.py`

Defines the Strategy protocol and implementations.

```mermaid
classDiagram
    class Strategy {
        <<Protocol>>
        +id: StrategyID
        +symbol: Symbol
        +on_signal: SignalCallback
        +run() None
        +stop() None
        +calculate_signal(candle: Candle) Action | None
    }
    class MovingAverageCrossStrategy {
        +id = MOVING_AVERAGE_CROSS
        +short_window: int
        +long_window: int
        +symbol: Symbol
        +run() None
        +stop() None
        +calculate_signal(candle: Candle) Action | None
    }
    
    Strategy <|.. MovingAverageCrossStrategy
```

**Key Concepts:**
- Strategies are stateless signal generators
- They receive candle data and emit Action signals (BUY/SELL)
- Multiple strategies can run concurrently on the same portfolio

---

### Portfolio

**File:** `src/goat/portfolio.py`

Central orchestrator that manages positions, strategies, and event flow.

```mermaid
classDiagram
    class Portfolio {
        +cash: float
        +total_value: float
        +positions: dict[Symbol, int]
        +data_handler: CandleDataHandler
        +execution_handler: ExecutionHandler
        +active_strategies: list[Strategy]
        +event_queue: deque[Event]
        +start() None
        +stop() None
        +add_strategy(strategy) None
        +remove_strategy(strategy) None
        +process_events() None
        +on_market(event, candle) None
        +on_signal(event) None
        +on_fill(event) None
    }
```

**Responsibilities:**
- Maintains cash and position state
- Manages active strategies lifecycle
- Processes events from the queue
- Converts signals to orders based on position sizing
- Updates positions from fill events

---

### Execution

**File:** `src/goat/execution.py`

Handles order lifecycle, internal matching, and external execution.

```mermaid
classDiagram
    class ExecutionHandler {
        +default_policy: ExecutionPolicyType
        +submit_order(...) tuple[Order, list[Fill]]
        +cancel_order(order_id) bool
        +get_order(order_id) Order | None
        +get_pending_orders(strategy_id) list[Order]
        +get_order_book(symbol) OrderBook
    }
    class OrderBook {
        +symbol: Symbol
        +add_order(order) list[Fill]
        +cancel_order(order_id) bool
        +best_bid: float | None
        +best_ask: float | None
        +spread: float | None
    }
    class Order {
        +order_id: UUID
        +strategy_id: str
        +symbol: Symbol
        +direction: Direction
        +order_type: OrderType
        +quantity: int
        +remaining_quantity: int
        +price: float
        +status: OrderStatus
        +fills: list[Fill]
        +apply_fill(qty, price) Fill
        +is_complete: bool
        +average_fill_price: float | None
    }
    class BaseExecutionPolicy {
        <<abstract>>
        +split_order(order) list[Order]
    }
    class ImmediatePolicy
    class TWAPPolicy {
        +num_chunks: int
        +interval_seconds: float
    }
    class IcebergPolicy {
        +visible_quantity: int
    }
    
    ExecutionHandler --> OrderBook
    ExecutionHandler --> BaseExecutionPolicy
    OrderBook --> Order
    BaseExecutionPolicy <|-- ImmediatePolicy
    BaseExecutionPolicy <|-- TWAPPolicy
    BaseExecutionPolicy <|-- IcebergPolicy
```

**Execution Flow:**
1. Receive order from Portfolio
2. Apply execution policy (split into chunks if needed)
3. Attempt internal matching via OrderBook
4. Route remaining quantity to external execution
5. Return fills for position updates

---

## Component Interactions

```mermaid
flowchart LR
    subgraph Enums["goat.enums"]
        Symbol
        Action
        Direction
        OrderType
        OrderStatus
    end
    
    subgraph Events["goat.event"]
        MarketEvent
        SignalEvent
        OrderEvent
        FillEvent
    end
    
    subgraph Data["goat.data_handler"]
        Candle
        CandleDataHandler
    end
    
    subgraph Strat["goat.strategy"]
        Strategy
    end
    
    subgraph Port["goat.portfolio"]
        Portfolio
    end
    
    subgraph Exec["goat.execution"]
        ExecutionHandler
        OrderBook
        Order
    end
    
    Enums --> Events
    Enums --> Data
    Enums --> Strat
    Enums --> Exec
    
    Data --> Port
    Strat --> Port
    Exec --> Port
    Events --> Port
```

---

## Usage Example

```python
from collections import deque
from goat.data_handler import HistoricDataHandler, Candle
from goat.event import MarketEvent, SignalEvent, FillEvent
from goat.execution import ExecutionHandler
from goat.portfolio import Portfolio
from goat.strategy import MovingAverageCrossStrategy
from goat.enums import Symbol, Direction, OrderType
import polars as pl

# 1. Setup data handler with historical data
df = pl.read_csv("historical_data.csv")
data_handler = HistoricDataHandler(df=df)

# 2. Setup execution handler
execution_handler = ExecutionHandler()

# 3. Create portfolio with initial cash
portfolio = Portfolio(
    cash=100_000.0,
    data_handler=data_handler,
    execution_handler=execution_handler,
)

# 4. Add strategy
strategy = MovingAverageCrossStrategy(
    short_window=10,
    long_window=30,
    symbol=Symbol.AAPL,
)
portfolio.add_strategy(strategy)

# 5. Main event loop
event_queue: deque = deque()

while True:
    # Get next candle
    candle = data_handler.next_candle()
    if candle is None:
        break
    
    # Emit market event
    event_queue.append(MarketEvent())
    
    # Process events
    while event_queue:
        event = event_queue.popleft()
        
        if event.event_type == "MARKET":
            # Feed candle to strategies
            for strat in portfolio.active_strategies or []:
                action = strat.calculate_signal(candle)
                if action:
                    signal = SignalEvent(
                        strategy_id=strat.id,
                        symbol=strat.symbol,
                        action=action,
                        datetime=candle.start_timestamp,
                    )
                    event_queue.append(signal)
        
        elif event.event_type == "SIGNAL":
            # Convert signal to order
            order, fills = execution_handler.submit_order(
                symbol=event.symbol,
                direction=Direction.BUY if event.action == Action.BUY else Direction.SELL,
                order_type=OrderType.LIMIT,
                quantity=10,
                price=candle.close,
                strategy_id=event.strategy_id,
            )
            # Queue fill events
            for fill in fills:
                event_queue.append(FillEvent(
                    fill_type="FULL" if order.is_complete else "PARTIAL",
                    order_id=fill.order_id,
                    quantity=fill.quantity,
                    price=fill.price,
                    datetime=fill.timestamp,
                ))
        
        elif event.event_type == "FILL":
            # Update portfolio positions
            portfolio.cash -= event.quantity * event.price
            # Update position tracking...

# 6. Stop all strategies
portfolio.stop()
```

---

## Enums Reference

| Enum | Values | Used By |
|------|--------|---------|
| `Symbol` | AAPL, TSLA | All modules |
| `Action` | BUY, SELL | Strategy signals |
| `Direction` | BUY, SELL | Order direction |
| `OrderType` | LIMIT, MARKET | Order specification |
| `OrderStatus` | PENDING, OPEN, PARTIALLY_FILLED, FILLED, CANCELLED | Order lifecycle |
| `ExecutionPolicyType` | IMMEDIATE, TWAP, ICEBERG | Order execution |

---

## Further Reading

- See `tests/test_execution.py` for comprehensive examples of order and execution behavior
- See `tests/test_event.py` for event validation examples

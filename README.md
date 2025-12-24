# goat
guler's op algo trading.

## Architecture

GOAT is an event-driven algorithmic trading framework with the following components:

```
DataHandler → MarketEvent → Strategy → SignalEvent → Portfolio → OrderEvent → ExecutionHandler → FillEvent
```

For detailed architecture documentation with diagrams, see **[ARCHITECTURE.md](ARCHITECTURE.md)**.

### Core Components

| Component | Description |
|-----------|-------------|
| **DataHandler** | Provides market data (historical or streaming) |
| **Strategy** | Generates trading signals from market data |
| **Portfolio** | Manages positions and converts signals to orders |
| **ExecutionHandler** | Executes orders with internal matching and external routing |
| **Events** | Typed messages (Market, Signal, Order, Fill) connecting components |

## Development

### Running Tests

```bash
# Run all tests (excludes slow/integration by default)
nox -s tests

# Run with specific Python version
nox -s tests -p 3.13

# Include slow tests
nox -s tests -- --run-slow-tests

# Include integration tests
nox -s tests -- --run-integration-tests

# Include both slow and integration tests
nox -s tests -- --run-slow-tests --run-integration-tests

# Run pytest directly (without nox coverage)
uv run pytest -v
uv run pytest -v --run-slow-tests
```

### Marking Tests

```python
from tests.conftest import slow_test, integration_test

@slow_test
def test_something_slow():
    ...

@integration_test
def test_with_external_service():
    ...
```

### Other Commands

```bash
# Lint and format
nox -s lint

# Type checking
nox -s typecheck

# Run all sessions
nox
```

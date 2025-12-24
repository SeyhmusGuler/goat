from goat.data_handler import CandleDataHandler
from goat.enums import Symbol
from goat.execution import ExecutionHandler
from goat.strategy import Strategy


class Portfolio:
    cash: float = 0.0
    total_value: float = 0.0
    positions: dict[Symbol, int] = {}
    data_handler: CandleDataHandler
    execution_handler: ExecutionHandler
    active_strategies: list[Strategy] | None = None

    def __init__(self, cash: float, data_handler: CandleDataHandler, execution_handler: ExecutionHandler) -> None:
        self.cash = cash
        self.total_value = cash
        self.data_handler = data_handler
        self.execution_handler = execution_handler

    def start(self) -> None:
        pass

    def stop(self) -> None:
        pass

    def add_strategy(self, strategy: Strategy) -> None:
        if self.active_strategies is None:
            self.active_strategies = []
        strategy.run()
        self.active_strategies.append(strategy)

    def remove_strategy(self, strategy: Strategy) -> None:
        if self.active_strategies is None:
            return
        strategy.stop()
        self.active_strategies.remove(strategy)

    def remove_strategies_by_id(self, strategy_id: str) -> None:
        if self.active_strategies is None:
            return
        for strategy in self.active_strategies:
            if strategy.id == strategy_id:
                strategy.stop()
        self.active_strategies = [strategy for strategy in self.active_strategies if strategy.id != strategy_id]

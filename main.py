from data.get_data import Requests
from strat.generic import Strategy
from strat.equal_weight_sp500 import EWSP


def print_hi(name):
    print(f"Hi, {name}")


if __name__ == "__main__":
    print_hi("Seyhmus")
    req = Requests()
    gen_strategy = Strategy(300)
    print(req)
    print(gen_strategy)
    gen_strategy.set_max_equity(100)
    print(gen_strategy)

    eqwe = EWSP()

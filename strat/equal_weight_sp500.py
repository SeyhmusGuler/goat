import pandas as pd
import math
from data.get_data import get_batch_data_from_stock_endpoint
from utils.utils import chunks

SP500_SYMBOLS_TEXTFILE = "data/sp500_symbols.txt"


def get_company_list_from_file():
    stocks = sorted(list(pd.read_csv(SP500_SYMBOLS_TEXTFILE, header=None)[0]))
    return stocks


def calculate_number_of_shares_to_buy(value):
    company_list = get_company_list_from_file()
    dollar_amount_per_stock = value / len(company_list)
    columns = ["Ticker", "Stock Price", "Market Capitalization", "Number of Shares to Buy"]
    result = pd.DataFrame(columns=columns)
    for symbols in chunks(company_list, 100):
        json_data = get_batch_data_from_stock_endpoint(symbols)
        for symbol in symbols:
            share_price = json_data[symbol]["quote"]["latestPrice"]
            market_cap = json_data[symbol]["quote"]["marketCap"]
            n_shares_to_buy = math.floor(dollar_amount_per_stock / share_price)
            result = result.append(
                pd.Series([symbol, share_price, market_cap, n_shares_to_buy], index=columns), ignore_index=True
            )
    return result


class EqualWeightSP:
    def __init__(self, dollar_amount=1000):
        self.tot_value = dollar_amount
        self.n_shares = calculate_number_of_shares_to_buy(self.tot_value)

    def __str__(self):
        return f"Equal weight sp500 with {self.tot_value} total value.\n {self.n_shares}"

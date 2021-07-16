import pandas as pd
import math
from data.get_data import get_latest_price

SP500_SYMBOLS_TEXTFILE = 'data/sp500_symbols.txt'


def get_company_list_from_file():
    stocks = sorted(list(pd.read_csv(SP500_SYMBOLS_TEXTFILE, header=None)[0]))
    return stocks


def calculate_number_of_shares_to_buy(value):
    company_list = get_company_list_from_file()
    dollar_amount_per_stock = value / len(company_list)
    n_shares_to_buy = {}
    for symbol in company_list:
        share_price = get_latest_price(symbol)
        n_shares_to_buy[symbol] = math.floor(dollar_amount_per_stock/share_price)
    return n_shares_to_buy


class EqualWeightSP:
    def __init__(self, dollar_amount=1000):
        self.tot_value = dollar_amount
        self.n_shares = pd.DataFrame.from_dict(
            calculate_number_of_shares_to_buy(self.tot_value),
            orient='index',
            columns=['nSharesToBuy']
        ).reset_index().rename(columns={'index': 'Symbol'})

    def __str__(self):
        return f'Equal weight sp500 with {self.tot_value} total value.\n {self.n_shares}'






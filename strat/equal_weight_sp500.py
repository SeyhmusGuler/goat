import pandas as pd
import numpy as np
import requests
import math
from secrets import stock_endpoint_url

SP500_SYMBOLS_TEXTFILE = 'data/sp500_symbols.txt'


def get_company_list_from_file():
    stocks = pd.read_csv(SP500_SYMBOLS_TEXTFILE, header=None)[0]
    return stocks


def get_price_from_api(symbol):
    pass


def get_market_cap_from_api(symbol):
    pass


def get_price_and_market_cap_from_api(symbol):
    api_symbol_url = stock_endpoint_url(symbol)
    data = requests.get(api_symbol_url)
    if data.status_code == 200:
        data_json = data.json()
        latest_price = data_json["latestPrice"]
        market_cap = data_json["marketCap"]
        return latest_price, market_cap
    else:
        ValueError("Status code returned from IEX Cloud API is not 200.")
        return None, None


def create():
    company_list = get_company_list_from_file()
    for symbol in company_list[:2]:
        price, market_cap = get_price_and_market_cap_from_api(symbol)
        if price and market_cap:
            print(f"Symbol: {symbol}, latest price: {price}, market capitalization: {market_cap}")


class EWSP:
    def __init__(self, max_eq=1000):
        self.max_eq = max_eq
        create()





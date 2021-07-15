from secrets import IEX_API_TOKEN, IEX_SANDBOX_BASE_URL
import requests


def stock_endpoint_url(symbol):
    return f"{IEX_SANDBOX_BASE_URL}/stable/stock/{symbol}/quote/?token={IEX_API_TOKEN}"


def get_json_data_from_stock_endpoint(symbol):
    api_symbol_url = stock_endpoint_url(symbol)
    data = requests.get(api_symbol_url)
    if data.status_code == 200:  # success
        json_data = data.json()
        return json_data
    else:
        ValueError("Status code returned from IEX Cloud API is not 200.")


def get_latest_price(symbol):
    data = get_json_data_from_stock_endpoint(symbol)
    return data["latestPrice"]


def get_market_cap(symbol):
    data = get_json_data_from_stock_endpoint(symbol)
    return data["marketCap"]

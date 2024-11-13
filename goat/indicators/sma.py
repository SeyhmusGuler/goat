import pandas as pd

def simple_moving_average(ts: pd.Series, window: int) -> pd.Series:
    return ts.rolling(window=window).mean()
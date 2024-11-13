from hypothesis import given, strategies as st
import pandas as pd
from goat.indicators.sma import simple_moving_average

@given(st.lists(st.floats(min_value=0, max_value=100), min_size=5, max_size=100))
def test_simple_moving_average(data):
    ts = pd.Series(data)
    window = 2
    expected = ts.rolling(window=window).mean()
    result = simple_moving_average(ts, window)
    assert result.equals(expected)
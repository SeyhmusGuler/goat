import numpy as np
import pytest
from hypothesis import given
from hypothesis import strategies as st
from pydantic import ValidationError

from goat.models.primitives import MAX_TIMESTAMP_NS, MIN_TIMESTAMP_NS, Candle, Tick, TickCandle, TimeCandle


@st.composite
def valid_numeric_candles(draw):
    high = draw(st.floats(allow_nan=False, allow_infinity=False))
    low = draw(st.floats(max_value=high, allow_nan=False, allow_infinity=False))
    open = draw(st.floats(min_value=low, max_value=high, allow_nan=False, allow_infinity=False))
    close = draw(st.floats(min_value=low, max_value=high, allow_nan=False, allow_infinity=False))
    volume = draw(st.integers(min_value=0))
    return {
        "high": high,
        "low": low,
        "open": open,
        "close": close,
        "volume": volume,
    }


@st.composite
def valid_numeric_candles_from_four_floats(draw):
    n1, n2, n3, n4 = draw(st.lists(st.floats(allow_nan=False, allow_infinity=False), min_size=4, max_size=4))
    return {
        "high": max(n1, n2, n3, n4),
        "low": min(n1, n2, n3, n4),
        "open": n1,
        "close": n4,
        "volume": 1,
    }


class TestTimestamp:
    def test_validate_min_max_timestamp_constraints(self):
        assert 0 <= MIN_TIMESTAMP_NS <= MAX_TIMESTAMP_NS < 2**64


class TestTick:
    @given(st.integers().filter(lambda x: MIN_TIMESTAMP_NS <= x <= MAX_TIMESTAMP_NS))
    def test_tick_timestamp_validation(self, timestamp):
        tick = Tick(timestamp=timestamp, price=1.0, volume=1)
        assert tick.timestamp == timestamp

    @given(volume=st.integers().filter(lambda x: x >= 0))
    def test_tick_volume_validation(self, volume):
        tick = Tick(timestamp=MIN_TIMESTAMP_NS, price=1.0, volume=volume)
        assert tick.volume == volume

    @given(st.integers().filter(lambda x: x < MIN_TIMESTAMP_NS or x > MAX_TIMESTAMP_NS))
    def test_tick_timestamp_validation_raises(self, timestamp):
        with pytest.raises(ValidationError):
            _: Tick = Tick(timestamp=timestamp, price=1.0, volume=1)

    @given(st.integers().filter(lambda x: x < 0))
    def test_tick_volume_validation_raises(self, volume):
        with pytest.raises(ValidationError):
            _: Tick = Tick(timestamp=MIN_TIMESTAMP_NS, price=1.0, volume=volume)

    @given(st.floats(allow_nan=False, allow_infinity=False))
    def test_tick_price_validation(self, price):
        tick = Tick(timestamp=MIN_TIMESTAMP_NS, price=price, volume=1)
        assert tick.price == price

    def test_tick_nan_inf_prices_disallowed(self):
        with pytest.raises(ValidationError):
            _: Tick = Tick(timestamp=MIN_TIMESTAMP_NS, price=np.nan, volume=1)
        with pytest.raises(ValidationError):
            _: Tick = Tick(timestamp=MIN_TIMESTAMP_NS, price=np.inf, volume=1)
        with pytest.raises(ValidationError):
            _: Tick = Tick(timestamp=MIN_TIMESTAMP_NS, price=-np.inf, volume=1)


class TestCandle:
    @given(valid_numeric_candles())
    def test_valid_candle(self, candle):
        candle = Candle(**candle)
        assert candle.low <= candle.open <= candle.high
        assert candle.low <= candle.close <= candle.high
        assert candle.volume >= 0

    @given(valid_numeric_candles_from_four_floats())
    def test_valid_candle_from_four_floats(self, candle):
        candle = Candle(**candle)
        assert candle.low <= candle.open <= candle.high
        assert candle.low <= candle.close <= candle.high
        assert candle.volume >= 0

    def test_nan_valued_candles(self):
        candle = Candle(high=np.nan, low=np.nan, open=np.nan, close=np.nan, volume=0)
        assert np.isnan(candle.high)
        assert np.isnan(candle.low)
        assert np.isnan(candle.open)
        assert np.isnan(candle.close)
        assert candle.volume == 0


class TestTimeCandle:
    # Timestamp validation
    def test_valid_timestamp_order(self):
        candle = TimeCandle(start_timestamp=100, end_timestamp=200)
        assert candle.start_timestamp == 100
        assert candle.end_timestamp == 200

    def test_equal_timestamps_valid(self):
        candle = TimeCandle(start_timestamp=100, end_timestamp=100)
        assert candle.start_timestamp == candle.end_timestamp

    def test_invalid_timestamp_order_raises(self):
        with pytest.raises(ValidationError, match="Candle start_timestamp must be less than or equal to end_timestamp"):
            TimeCandle(start_timestamp=200, end_timestamp=100)

    # Update from Tick
    def test_update_from_tick_sets_open_when_nan(self):
        candle = TimeCandle(start_timestamp=0, end_timestamp=100)
        assert np.isnan(candle.open)
        candle.update(Tick(timestamp=50, price=10.0, volume=5))
        assert candle.open == 10.0
        assert candle.close == 10.0
        assert candle.high == 10.0
        assert candle.low == 10.0
        assert candle.volume == 5

    def test_update_from_tick_preserves_open(self):
        candle = TimeCandle(start_timestamp=0, end_timestamp=100)
        candle.update(Tick(timestamp=10, price=10.0, volume=1))
        candle.update(Tick(timestamp=50, price=20.0, volume=2))
        assert candle.open == 10.0
        assert candle.close == 20.0
        assert candle.high == 20.0
        assert candle.low == 10.0
        assert candle.volume == 3

    def test_update_from_tick_updates_high_low(self):
        candle = TimeCandle(start_timestamp=0, end_timestamp=100)
        candle.update(Tick(timestamp=10, price=50.0, volume=1))
        candle.update(Tick(timestamp=20, price=100.0, volume=1))
        candle.update(Tick(timestamp=30, price=25.0, volume=1))
        assert candle.high == 100.0
        assert candle.low == 25.0

    def test_update_from_tick_outside_window_raises(self):
        candle = TimeCandle(start_timestamp=100, end_timestamp=200)

        with pytest.raises(ValueError, match="Tick timestamp is outside the candle time window"):
            candle.update(Tick(timestamp=50, price=10.0, volume=1))
        with pytest.raises(ValueError, match="Tick timestamp is outside the candle time window"):
            candle.update(Tick(timestamp=250, price=10.0, volume=1))

    def test_update_from_tick_at_boundaries_valid(self):
        candle = TimeCandle(start_timestamp=100, end_timestamp=200)
        candle.update(Tick(timestamp=100, price=10.0, volume=1))
        candle.update(Tick(timestamp=200, price=20.0, volume=1))
        assert candle.open == 10.0
        assert candle.close == 20.0

    # Update from Candle
    def test_update_from_candle_valid_contained(self):
        parent = TimeCandle(start_timestamp=0, end_timestamp=100)
        child = TimeCandle(start_timestamp=25, end_timestamp=75)
        child.update(Tick(timestamp=50, price=10.0, volume=5))
        parent.update(child)
        assert parent.high == 10.0
        assert parent.low == 10.0
        assert parent.volume == 5

    def test_update_from_candle_before_start_raises(self):
        parent = TimeCandle(start_timestamp=100, end_timestamp=200)
        child = TimeCandle(start_timestamp=50, end_timestamp=150)
        with pytest.raises(ValueError, match="New candle time window is outside the candle time window"):
            parent.update(child)

    def test_update_from_candle_after_end_raises(self):
        parent = TimeCandle(start_timestamp=100, end_timestamp=200)
        child = TimeCandle(start_timestamp=150, end_timestamp=250)
        with pytest.raises(ValueError, match="New candle time window is outside the candle time window"):
            parent.update(child)

    # Open Price Logic
    def test_update_from_candle_sets_open_when_both_nan(self):
        parent = TimeCandle(start_timestamp=0, end_timestamp=100)
        child = TimeCandle(start_timestamp=0, end_timestamp=50, open=10)
        parent.update(child)
        assert parent.open == 10.0

    def test_update_from_candle_preserves_open_when_child_nan(self):
        parent = TimeCandle(start_timestamp=0, end_timestamp=100, open=15)
        child = TimeCandle(start_timestamp=50, end_timestamp=50)
        parent.update(child)
        assert parent.open == 15.0

    def test_update_from_candle_open_matches_succeeds(self):
        parent = TimeCandle(start_timestamp=0, end_timestamp=100, open=10.0)
        child = TimeCandle(start_timestamp=0, end_timestamp=50, open=10.0)
        parent.update(child)
        assert parent.open == 10.0

    def test_update_from_candle_open_differs_raises(self):
        parent = TimeCandle(start_timestamp=0, end_timestamp=100, open=10.0)
        child = TimeCandle(start_timestamp=0, end_timestamp=50, open=20.0)
        with pytest.raises(ValueError, match="Candle open price is different"):
            parent.update(child)

    def test_update_from_candle_open_not_checked_when_timestamps_differ(self):
        parent = TimeCandle(start_timestamp=0, end_timestamp=100, open=10.0)
        child = TimeCandle(start_timestamp=25, end_timestamp=75, open=999.0)
        parent.update(child)
        assert parent.open == 10.0

    # Close Price Logic
    def test_update_from_candle_sets_close_when_both_nan(self):
        parent = TimeCandle(start_timestamp=0, end_timestamp=100)
        child = TimeCandle(start_timestamp=50, end_timestamp=100, close=30.0)
        parent.update(child)
        assert parent.close == 30.0

    def test_update_from_candle_preserves_close_when_child_nan(self):
        parent = TimeCandle(start_timestamp=0, end_timestamp=100, close=25.0)
        child = TimeCandle(start_timestamp=50, end_timestamp=99)
        parent.update(child)
        assert parent.close == 25.0

    def test_update_from_candle_close_matches_succeeds(self):
        parent = TimeCandle(start_timestamp=0, end_timestamp=100, close=30.0)
        child = TimeCandle(start_timestamp=50, end_timestamp=100, close=30.0)
        parent.update(child)
        assert parent.close == 30.0

    def test_update_from_candle_close_differs_raises(self):
        parent = TimeCandle(start_timestamp=0, end_timestamp=100, close=30.0)
        child = TimeCandle(start_timestamp=50, end_timestamp=100, close=40.0)
        with pytest.raises(ValueError, match="Candle close price is different"):
            parent.update(child)

    def test_update_from_candle_close_not_checked_when_timestamps_differ(self):
        parent = TimeCandle(start_timestamp=0, end_timestamp=100, close=30.0)
        child = TimeCandle(start_timestamp=25, end_timestamp=75, close=999.0)
        parent.update(child)
        assert parent.close == 30.0

    # High/Low/Volume Accumulation
    def test_update_from_candle_accumulates_volume(self):
        parent = TimeCandle(start_timestamp=0, end_timestamp=100)
        parent.update(Tick(timestamp=10, price=10.0, volume=5))
        child = TimeCandle(start_timestamp=50, end_timestamp=75)
        child.update(Tick(timestamp=60, price=20.0, volume=10))
        parent.update(child)
        assert parent.volume == 15

    def test_update_from_candle_updates_high(self):
        parent = TimeCandle(start_timestamp=0, end_timestamp=100)
        parent.update(Tick(timestamp=10, price=50.0, volume=1))
        child = TimeCandle(start_timestamp=50, end_timestamp=75)
        child.update(Tick(timestamp=60, price=100.0, volume=1))
        parent.update(child)
        assert parent.high == 100.0

    def test_update_from_candle_updates_low(self):
        parent = TimeCandle(start_timestamp=0, end_timestamp=100)
        parent.update(Tick(timestamp=10, price=50.0, volume=1))
        child = TimeCandle(start_timestamp=50, end_timestamp=75)
        child.update(Tick(timestamp=60, price=25.0, volume=1))
        parent.update(child)
        assert parent.low == 25.0

    def test_update_with_invalid_type_raises(self):
        candle = TimeCandle(start_timestamp=0, end_timestamp=100)
        with pytest.raises(TypeError, match="Update data must be a Tick or a Candle"):
            candle.update("invalid")  # type: ignore[no-matching-overload]


class TestTickCandle:
    def test_valid_tick_candle_creation(self):
        candle = TickCandle(start_timestamp=100, max_ticks=10)
        assert candle.start_timestamp == 100
        assert candle.max_ticks == 10
        assert candle.num_ticks == 0

    def test_max_ticks_must_be_positive(self):
        with pytest.raises(ValidationError, match="greater than 0"):
            TickCandle(start_timestamp=0, max_ticks=0)
        with pytest.raises(ValidationError, match="greater than 0"):
            TickCandle(start_timestamp=0, max_ticks=-1)

    def test_num_ticks_cannot_exceed_max_ticks(self):
        with pytest.raises(ValidationError, match="Tick count is greater than maximum tick count"):
            TickCandle(start_timestamp=0, max_ticks=5, num_ticks=10)

    def test_num_ticks_equal_to_max_ticks_valid(self):
        candle = TickCandle(start_timestamp=0, max_ticks=5, num_ticks=5)
        assert candle.num_ticks == candle.max_ticks

    def test_update_sets_open_when_nan(self):
        candle = TickCandle(start_timestamp=0, max_ticks=10)
        assert np.isnan(candle.open)
        candle.update(Tick(timestamp=50, price=10.0, volume=5))
        assert candle.open == 10.0
        assert candle.close == 10.0
        assert candle.high == 10.0
        assert candle.low == 10.0
        assert candle.volume == 5
        assert candle.num_ticks == 1

    def test_update_preserves_open(self):
        candle = TickCandle(start_timestamp=0, max_ticks=10)
        candle.update(Tick(timestamp=0, price=10.0, volume=1))
        candle.update(Tick(timestamp=0, price=20.0, volume=2))
        assert candle.open == 10.0
        assert candle.close == 20.0
        assert candle.num_ticks == 2

    def test_update_tracks_high(self):
        candle = TickCandle(start_timestamp=0, max_ticks=10)
        candle.update(Tick(timestamp=10, price=50.0, volume=1))
        candle.update(Tick(timestamp=20, price=100.0, volume=1))
        candle.update(Tick(timestamp=30, price=75.0, volume=1))
        assert candle.high == 100.0

    def test_update_tracks_low(self):
        candle = TickCandle(start_timestamp=0, max_ticks=10)
        candle.update(Tick(timestamp=10, price=50.0, volume=1))
        candle.update(Tick(timestamp=20, price=25.0, volume=1))
        candle.update(Tick(timestamp=30, price=75.0, volume=1))
        assert candle.low == 25.0

    def test_update_updates_close_when_newest(self):
        candle = TickCandle(start_timestamp=0, max_ticks=10)
        candle.update(Tick(timestamp=10, price=10.0, volume=1))
        assert candle.close == 10.0
        candle.update(Tick(timestamp=20, price=20.0, volume=1))
        assert candle.close == 20.0
        candle.update(Tick(timestamp=30, price=15.0, volume=1))
        assert candle.close == 15.0
        candle.update(Tick(timestamp=10, price=25.0, volume=1))
        assert candle.close == 15.0

    def test_update_accumulates_volume(self):
        candle = TickCandle(start_timestamp=0, max_ticks=10)
        candle.update(Tick(timestamp=10, price=10.0, volume=5))
        candle.update(Tick(timestamp=20, price=20.0, volume=10))
        candle.update(Tick(timestamp=30, price=30.0, volume=3))
        assert candle.volume == 18

    def test_update_increments_tick_count(self):
        candle = TickCandle(start_timestamp=0, max_ticks=10)
        assert candle.num_ticks == 0
        candle.update(Tick(timestamp=10, price=10.0, volume=1))
        assert candle.num_ticks == 1
        candle.update(Tick(timestamp=20, price=20.0, volume=1))
        assert candle.num_ticks == 2

    def test_update_raises_when_candle_full(self):
        candle = TickCandle(start_timestamp=0, max_ticks=2)
        candle.update(Tick(timestamp=10, price=10.0, volume=1))
        candle.update(Tick(timestamp=20, price=20.0, volume=1))
        with pytest.raises(ValueError, match="TickCandle is full"):
            candle.update(Tick(timestamp=30, price=30.0, volume=1))

    def test_update_allows_max_ticks_exactly(self):
        candle = TickCandle(start_timestamp=0, max_ticks=3)
        candle.update(Tick(timestamp=10, price=10.0, volume=1))
        candle.update(Tick(timestamp=20, price=20.0, volume=1))
        candle.update(Tick(timestamp=30, price=30.0, volume=1))
        assert candle.num_ticks == 3
        with pytest.raises(ValueError, match="TickCandle is full"):
            candle.update(Tick(timestamp=40, price=40.0, volume=1))

    def test_update_raises_when_tick_before_start(self):
        candle = TickCandle(start_timestamp=100, max_ticks=10)
        with pytest.raises(ValueError, match="Tick timestamp is before the candle start timestamp"):
            candle.update(Tick(timestamp=50, price=10.0, volume=1))

    def test_update_allows_tick_at_start_timestamp(self):
        candle = TickCandle(start_timestamp=100, max_ticks=10)
        candle.update(Tick(timestamp=100, price=10.0, volume=1))
        assert candle.num_ticks == 1

    def test_update_allows_tick_after_start_timestamp(self):
        candle = TickCandle(start_timestamp=100, max_ticks=10)
        candle.update(Tick(timestamp=200, price=10.0, volume=1))
        assert candle.num_ticks == 1

    def test_str_representation(self):
        candle = TickCandle(start_timestamp=100, max_ticks=5, num_ticks=2)
        candle.open = 10.0
        candle.high = 20.0
        candle.low = 5.0
        candle.close = 15.0
        candle.volume = 100
        s = str(candle)
        assert "TickCandle" in s
        assert "start=100" in s
        assert "max_ticks=5" in s
        assert "num_ticks=2" in s

    def test_single_tick_candle(self):
        candle = TickCandle(start_timestamp=0, max_ticks=1)
        candle.update(Tick(timestamp=10, price=50.0, volume=10))
        assert candle.open == 50.0
        assert candle.high == 50.0
        assert candle.low == 50.0
        assert candle.close == 50.0
        assert candle.volume == 10
        assert candle.num_ticks == 1
        with pytest.raises(ValueError, match="TickCandle is full"):
            candle.update(Tick(timestamp=20, price=60.0, volume=5))

    def test_zero_volume_ticks(self):
        candle = TickCandle(start_timestamp=0, max_ticks=10)
        candle.update(Tick(timestamp=10, price=10.0, volume=0))
        candle.update(Tick(timestamp=20, price=20.0, volume=0))
        assert candle.volume == 0
        assert candle.num_ticks == 2

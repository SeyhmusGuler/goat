import numpy as np
import pytest
from pydantic import ValidationError

from goat.models.primitives import MAX_TIMESTAMP_NS, MIN_TIMESTAMP_NS, Tick, TimeWindowCandle


class TestTimestamp:
    def test_validate_min_max_timestamp_constraints(self):
        assert 0 <= MIN_TIMESTAMP_NS <= MAX_TIMESTAMP_NS < 2**64


class TestTimeWindowCandle:
    """Tests for TimeWindowCandle covering all if/else branches."""

    # Timestamp validation
    def test_valid_timestamp_order(self):
        candle = TimeWindowCandle(start_timestamp=100, end_timestamp=200)
        assert candle.start_timestamp == 100
        assert candle.end_timestamp == 200

    def test_equal_timestamps_valid(self):
        candle = TimeWindowCandle(start_timestamp=100, end_timestamp=100)
        assert candle.start_timestamp == candle.end_timestamp

    def test_invalid_timestamp_order_raises(self):
        with pytest.raises(ValidationError, match="start_timestamp must be less than or equal to end_timestamp"):
            TimeWindowCandle(start_timestamp=200, end_timestamp=100)

    # Update from Tick
    def test_update_from_tick_sets_open_when_nan(self):
        candle = TimeWindowCandle(start_timestamp=0, end_timestamp=100)
        assert np.isnan(candle.open)
        candle.update(Tick(timestamp=50, price=10.0, volume=5))
        assert candle.open == 10.0
        assert candle.close == 10.0
        assert candle.high == 10.0
        assert candle.low == 10.0
        assert candle.volume == 5

    def test_update_from_tick_preserves_open(self):
        candle = TimeWindowCandle(start_timestamp=0, end_timestamp=100)
        candle.update(Tick(timestamp=10, price=10.0, volume=1))
        candle.update(Tick(timestamp=50, price=20.0, volume=2))
        assert candle.open == 10.0
        assert candle.close == 20.0
        assert candle.high == 20.0
        assert candle.low == 10.0
        assert candle.volume == 3

    def test_update_from_tick_updates_high_low(self):
        candle = TimeWindowCandle(start_timestamp=0, end_timestamp=100)
        candle.update(Tick(timestamp=10, price=50.0, volume=1))
        candle.update(Tick(timestamp=20, price=100.0, volume=1))
        candle.update(Tick(timestamp=30, price=25.0, volume=1))
        assert candle.high == 100.0
        assert candle.low == 25.0

    def test_update_from_tick_outside_window_raises(self):
        candle = TimeWindowCandle(start_timestamp=100, end_timestamp=200)

        with pytest.raises(ValueError, match="Tick timestamp is outside the candle time window"):
            candle.update(Tick(timestamp=50, price=10.0, volume=1))
        with pytest.raises(ValueError, match="Tick timestamp is outside the candle time window"):
            candle.update(Tick(timestamp=250, price=10.0, volume=1))

    def test_update_from_tick_at_boundaries_valid(self):
        candle = TimeWindowCandle(start_timestamp=100, end_timestamp=200)
        candle.update(Tick(timestamp=100, price=10.0, volume=1))
        candle.update(Tick(timestamp=200, price=20.0, volume=1))
        assert candle.open == 10.0
        assert candle.close == 20.0

    # Update from Candle
    def test_update_from_candle_valid_contained(self):
        parent = TimeWindowCandle(start_timestamp=0, end_timestamp=100)
        child = TimeWindowCandle(start_timestamp=25, end_timestamp=75)
        child.update(Tick(timestamp=50, price=10.0, volume=5))
        parent.update(child)
        assert parent.high == 10.0
        assert parent.low == 10.0
        assert parent.volume == 5

    def test_update_from_candle_before_start_raises(self):
        parent = TimeWindowCandle(start_timestamp=100, end_timestamp=200)
        child = TimeWindowCandle(start_timestamp=50, end_timestamp=150)
        with pytest.raises(ValueError, match="New candle time window is outside the candle time window"):
            parent.update(child)

    def test_update_from_candle_after_end_raises(self):
        parent = TimeWindowCandle(start_timestamp=100, end_timestamp=200)
        child = TimeWindowCandle(start_timestamp=150, end_timestamp=250)
        with pytest.raises(ValueError, match="New candle time window is outside the candle time window"):
            parent.update(child)

    # Open Price Logic
    def test_update_from_candle_sets_open_when_both_nan(self):
        parent = TimeWindowCandle(start_timestamp=0, end_timestamp=100)
        child = TimeWindowCandle(start_timestamp=0, end_timestamp=50, open=10)
        parent.update(child)
        assert parent.open == 10.0

    def test_update_from_candle_preserves_open_when_child_nan(self):
        parent = TimeWindowCandle(start_timestamp=0, end_timestamp=100, open=15)
        child = TimeWindowCandle(start_timestamp=0, end_timestamp=50)
        parent.update(child)
        assert parent.open == 15.0

    def test_update_from_candle_open_matches_succeeds(self):
        parent = TimeWindowCandle(start_timestamp=0, end_timestamp=100, open=10.0)
        child = TimeWindowCandle(start_timestamp=0, end_timestamp=50, open=10.0)
        parent.update(child)
        assert parent.open == 10.0

    def test_update_from_candle_open_differs_raises(self):
        parent = TimeWindowCandle(start_timestamp=0, end_timestamp=100, open=10.0)
        child = TimeWindowCandle(start_timestamp=0, end_timestamp=50, open=20.0)
        with pytest.raises(ValueError, match="Candle open price is different"):
            parent.update(child)

    def test_update_from_candle_open_not_checked_when_timestamps_differ(self):
        parent = TimeWindowCandle(start_timestamp=0, end_timestamp=100, open=10.0)
        child = TimeWindowCandle(start_timestamp=25, end_timestamp=75, open=999.0)
        parent.update(child)
        assert parent.open == 10.0

    # Close Price Logic
    def test_update_from_candle_sets_close_when_both_nan(self):
        parent = TimeWindowCandle(start_timestamp=0, end_timestamp=100)
        child = TimeWindowCandle(start_timestamp=50, end_timestamp=100, close=30.0)
        parent.update(child)
        assert parent.close == 30.0

    def test_update_from_candle_preserves_close_when_child_nan(self):
        parent = TimeWindowCandle(start_timestamp=0, end_timestamp=100, close=25.0)
        child = TimeWindowCandle(start_timestamp=50, end_timestamp=100)
        parent.update(child)
        assert parent.close == 25.0

    def test_update_from_candle_close_matches_succeeds(self):
        parent = TimeWindowCandle(start_timestamp=0, end_timestamp=100, close=30.0)
        child = TimeWindowCandle(start_timestamp=50, end_timestamp=100, close=30.0)
        parent.update(child)
        assert parent.close == 30.0

    def test_update_from_candle_close_differs_raises(self):
        parent = TimeWindowCandle(start_timestamp=0, end_timestamp=100, close=30.0)
        child = TimeWindowCandle(start_timestamp=50, end_timestamp=100, close=40.0)
        with pytest.raises(ValueError, match="Candle close price is different"):
            parent.update(child)

    def test_update_from_candle_close_not_checked_when_timestamps_differ(self):
        parent = TimeWindowCandle(start_timestamp=0, end_timestamp=100, close=30.0)
        child = TimeWindowCandle(start_timestamp=25, end_timestamp=75, close=999.0)
        parent.update(child)
        assert parent.close == 30.0

    # High/Low/Volume Accumulation
    def test_update_from_candle_accumulates_volume(self):
        parent = TimeWindowCandle(start_timestamp=0, end_timestamp=100)
        parent.update(Tick(timestamp=10, price=10.0, volume=5))
        child = TimeWindowCandle(start_timestamp=50, end_timestamp=75)
        child.update(Tick(timestamp=60, price=20.0, volume=10))
        parent.update(child)
        assert parent.volume == 15

    def test_update_from_candle_updates_high(self):
        parent = TimeWindowCandle(start_timestamp=0, end_timestamp=100)
        parent.update(Tick(timestamp=10, price=50.0, volume=1))
        child = TimeWindowCandle(start_timestamp=50, end_timestamp=75)
        child.update(Tick(timestamp=60, price=100.0, volume=1))
        parent.update(child)
        assert parent.high == 100.0

    def test_update_from_candle_updates_low(self):
        parent = TimeWindowCandle(start_timestamp=0, end_timestamp=100)
        parent.update(Tick(timestamp=10, price=50.0, volume=1))
        child = TimeWindowCandle(start_timestamp=50, end_timestamp=75)
        child.update(Tick(timestamp=60, price=25.0, volume=1))
        parent.update(child)
        assert parent.low == 25.0

    def test_update_with_invalid_type_raises(self):
        candle = TimeWindowCandle(start_timestamp=0, end_timestamp=100)
        with pytest.raises(TypeError, match="data must be a Tick or a Candle"):
            candle.update("invalid")  # type: ignore[no-matching-overload]

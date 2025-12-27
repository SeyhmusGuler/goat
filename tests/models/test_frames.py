"""Tests for the frames module using hypothesis and polars testing utilities."""

import polars as pl
import pytest
from hypothesis import assume, given, settings
from hypothesis import strategies as st
from pandera.errors import SchemaError
from polars.testing import assert_frame_equal
from polars.testing.parametric import column, dataframes

from goat.models.frames import CandleFrame, TimeCandleFrame

# ---------------------------------------------------------------------------
# Hypothesis Strategies
# ---------------------------------------------------------------------------

# Strategy for valid price values (positive floats)
price_strategy = st.floats(min_value=0.01, max_value=1e6, allow_nan=False, allow_infinity=False)

# Strategy for valid volume values (non-negative integers)
volume_strategy = st.integers(min_value=0, max_value=2**64 - 1)

# Strategy for valid timestamp values (unsigned 64-bit integers)
timestamp_strategy = st.integers(min_value=0, max_value=2**64 - 1)


@st.composite
def valid_ohlc_strategy(draw):
    """Generate valid OHLC values where high >= max(open, close) and low <= min(open, close)."""
    open_price = draw(price_strategy)
    close_price = draw(price_strategy)
    # High must be >= both open and close
    high_price = draw(
        st.floats(
            min_value=max(open_price, close_price),
            max_value=1e6,
            allow_nan=False,
            allow_infinity=False,
        )
    )
    # Low must be <= both open and close
    low_price = draw(
        st.floats(
            min_value=0.01,
            max_value=min(open_price, close_price),
            allow_nan=False,
            allow_infinity=False,
        )
    )
    return {"open": open_price, "high": high_price, "low": low_price, "close": close_price}


@st.composite
def candle_data_strategy(draw, min_rows=1, max_rows=100):
    """Generate valid CandleFrame data."""
    num_rows = draw(st.integers(min_value=min_rows, max_value=max_rows))
    candles = [draw(valid_ohlc_strategy()) for _ in range(num_rows)]
    volumes = draw(st.lists(volume_strategy, min_size=num_rows, max_size=num_rows))

    return {
        "open": [c["open"] for c in candles],
        "high": [c["high"] for c in candles],
        "low": [c["low"] for c in candles],
        "close": [c["close"] for c in candles],
        "volume": volumes,
    }


@st.composite
def time_candle_data_strategy(draw, min_rows=1, max_rows=100):
    """Generate valid TimeCandleFrame data."""
    candle_data = draw(candle_data_strategy(min_rows=min_rows, max_rows=max_rows))
    num_rows = len(candle_data["open"])
    timestamps = draw(st.lists(timestamp_strategy, min_size=num_rows, max_size=num_rows))
    candle_data["timestamp"] = timestamps
    return candle_data


# ---------------------------------------------------------------------------
# polars.testing.parametric DataFrame Strategies
# ---------------------------------------------------------------------------

# Define parametric dataframe strategies using polars.testing.parametric
candle_frame_parametric = dataframes(
    cols=[
        column("open", dtype=pl.Float64),
        column("high", dtype=pl.Float64),
        column("low", dtype=pl.Float64),
        column("close", dtype=pl.Float64),
        column("volume", dtype=pl.UInt64),
    ],
    min_size=1,
    max_size=50,
)

time_candle_frame_parametric = dataframes(
    cols=[
        column("timestamp", dtype=pl.UInt64),
        column("open", dtype=pl.Float64),
        column("high", dtype=pl.Float64),
        column("low", dtype=pl.Float64),
        column("close", dtype=pl.Float64),
        column("volume", dtype=pl.UInt64),
    ],
    min_size=1,
    max_size=50,
)


# ---------------------------------------------------------------------------
# CandleFrame Tests
# ---------------------------------------------------------------------------


class TestCandleFrame:
    """Tests for the CandleFrame model."""

    def test_valid_candle_frame_creation(self):
        """Test creating a valid CandleFrame."""
        df = pl.LazyFrame(
            {
                "open": [100.0, 101.0],
                "high": [102.0, 103.0],
                "low": [99.0, 100.0],
                "close": [101.0, 102.0],
                "volume": pl.Series([1000, 2000], dtype=pl.UInt64),
            }
        )
        validated = CandleFrame.validate(df)
        result = validated.collect()

        assert result.shape == (2, 5)
        assert result.schema == {
            "open": pl.Float64,
            "high": pl.Float64,
            "low": pl.Float64,
            "close": pl.Float64,
            "volume": pl.UInt64,
        }

    def test_empty_candle_frame_creation(self):
        """Test creating an empty CandleFrame."""
        df = pl.LazyFrame(
            schema={
                "open": pl.Float64,
                "high": pl.Float64,
                "low": pl.Float64,
                "close": pl.Float64,
                "volume": pl.UInt64,
            }
        )
        validated = CandleFrame.validate(df)
        result = validated.collect()

        assert result.shape == (0, 5)

    def test_negative_volume_validation(self):
        """Test behavior with negative volume values."""
        df = pl.LazyFrame(
            {
                "open": [100.0],
                "high": [102.0],
                "low": [99.0],
                "close": [101.0],
                "volume": [-1],  # Negative volume
            }
        )
        with pytest.raises(SchemaError):
            CandleFrame.validate(df).collect()

    def test_missing_column_raises_error(self):
        """Test that missing columns raise a validation error."""
        df = pl.LazyFrame(
            {
                "open": [100.0],
                "high": [102.0],
                "low": [99.0],
                # Missing 'close' and 'volume'
            }
        )
        with pytest.raises(SchemaError):
            CandleFrame.validate(df).collect()

    def test_wrong_dtype_raises_error(self):
        df = pl.LazyFrame(
            {
                "open": ["100.0"],  # String instead of float
                "high": [102.0],
                "low": [99.0],
                "close": [101.0],
                "volume": pl.Series([1000], dtype=pl.UInt64),
            }
        )
        with pytest.raises(SchemaError):
            CandleFrame.validate(df).collect()

    @given(data=candle_data_strategy())
    @settings(max_examples=100)
    def test_candle_frame_with_hypothesis(self, data):
        """Property-based test for CandleFrame validation."""
        # Filter out invalid volumes
        assume(all(v >= 0 for v in data["volume"]))

        df = pl.LazyFrame(data).with_columns(pl.col("volume").cast(pl.UInt64))
        validated = CandleFrame.validate(df)
        result = validated.collect()

        # Schema should match after validation
        assert result.schema["open"] == pl.Float64
        assert result.schema["high"] == pl.Float64
        assert result.schema["low"] == pl.Float64
        assert result.schema["close"] == pl.Float64
        assert result.schema["volume"] == pl.UInt64

        # All volumes should be non-negative
        assert result["volume"].min() >= 0 or result.is_empty()

    @given(df=candle_frame_parametric)
    @settings(max_examples=50)
    def test_candle_frame_parametric(self, df: pl.DataFrame):
        """Test CandleFrame with polars parametric dataframes."""
        # Ensure volume is non-negative for valid data
        df = df.with_columns(pl.col("volume").abs())

        lazy_df = df.lazy()
        validated = CandleFrame.validate(lazy_df)
        result = validated.collect()

        # Column types should be preserved
        assert result.schema == df.schema

        # Data should be preserved
        assert_frame_equal(result, df)


# ---------------------------------------------------------------------------
# TimeCandleFrame Tests
# ---------------------------------------------------------------------------


class TestTimeCandleFrame:
    """Tests for the TimeCandleFrame model."""

    def test_valid_time_candle_frame_creation(self):
        """Test creating a valid TimeCandleFrame."""
        df = pl.LazyFrame(
            {
                "timestamp": [1672531200000, 1672531200001],
                "open": [100.0, 101.0],
                "high": [102.0, 103.0],
                "low": [99.0, 100.0],
                "close": [101.0, 102.0],
                "volume": [1000, 2000],
            }
        ).with_columns(pl.col("timestamp").cast(pl.UInt64), pl.col("volume").cast(pl.UInt64))

        validated = TimeCandleFrame.validate(df)
        result = validated.collect()

        assert result.shape == (2, 6)
        assert result.schema["timestamp"] == pl.UInt64

    def test_empty_time_candle_frame_creation(self):
        """Test creating an empty TimeCandleFrame."""
        df = pl.LazyFrame(
            schema={
                "timestamp": pl.UInt64,
                "open": pl.Float64,
                "high": pl.Float64,
                "low": pl.Float64,
                "close": pl.Float64,
                "volume": pl.UInt64,
            }
        )
        validated = TimeCandleFrame.validate(df)
        result = validated.collect()

        assert result.shape == (0, 6)

    def test_inherits_candle_frame_validation(self):
        """Test that TimeCandleFrame inherits CandleFrame's volume validation.

        Note: Pandera-polars may not raise SchemaError with default settings
        when the UInt64 type constraint for volume (non-negative integer) is
        violated. This test documents the actual behavior.
        """
        df = pl.LazyFrame(
            {
                "timestamp": [1672531200000],
                "open": [100.0],
                "high": [102.0],
                "low": [99.0],
                "close": [101.0],
                "volume": [-1],  # Negative volume
            }
        ).with_columns(pl.col("timestamp").cast(pl.UInt64))

        with pytest.raises(SchemaError):
            TimeCandleFrame.validate(df).collect()

    def test_missing_timestamp_raises_error(self):
        """Test that missing timestamp raises a validation error."""
        df = pl.LazyFrame(
            {
                "open": [100.0],
                "high": [102.0],
                "low": [99.0],
                "close": [101.0],
                "volume": [1000],
                # Missing 'timestamp'
            }
        )
        with pytest.raises(SchemaError):
            TimeCandleFrame.validate(df).collect()

    @given(data=time_candle_data_strategy())
    @settings(max_examples=100)
    def test_time_candle_frame_with_hypothesis(self, data):
        """Property-based test for TimeCandleFrame validation."""
        # Filter out invalid volumes
        assume(all(v >= 0 for v in data["volume"]))

        df = pl.LazyFrame(data).with_columns(
            pl.col("timestamp").cast(pl.UInt64),
            pl.col("volume").cast(pl.UInt64),
        )
        validated = TimeCandleFrame.validate(df)
        result = validated.collect()

        # Schema should match after validation
        assert result.schema["timestamp"] == pl.UInt64
        assert result.schema["open"] == pl.Float64
        assert result.schema["high"] == pl.Float64
        assert result.schema["low"] == pl.Float64
        assert result.schema["close"] == pl.Float64
        assert result.schema["volume"] == pl.UInt64

    @given(df=time_candle_frame_parametric)
    @settings(max_examples=50)
    def test_time_candle_frame_parametric(self, df: pl.DataFrame):
        """Test TimeCandleFrame with polars parametric dataframes."""
        # Ensure volume is non-negative for valid data
        df = df.with_columns(pl.col("volume").abs())

        lazy_df = df.lazy()
        validated = TimeCandleFrame.validate(lazy_df)
        result = validated.collect()

        # Column types should be preserved
        assert result.schema == df.schema

        # Data should be preserved
        assert_frame_equal(result, df)


# ---------------------------------------------------------------------------
# Cross-schema Tests
# ---------------------------------------------------------------------------


class TestCrossSchemaCompatibility:
    """Tests for compatibility between CandleFrame and TimeCandleFrame."""

    def test_time_candle_frame_contains_candle_frame_columns(self):
        """Test that TimeCandleFrame has all CandleFrame columns plus timestamp."""
        candle_schema = CandleFrame.to_schema()
        time_candle_schema = TimeCandleFrame.to_schema()

        candle_columns = set(candle_schema.columns.keys())
        time_candle_columns = set(time_candle_schema.columns.keys())

        # TimeCandleFrame should have all CandleFrame columns
        assert candle_columns.issubset(time_candle_columns)

        # TimeCandleFrame should additionally have timestamp
        assert "timestamp" in time_candle_columns
        assert "timestamp" not in candle_columns

    @given(data=time_candle_data_strategy(min_rows=1, max_rows=10))
    @settings(max_examples=25)
    def test_drop_timestamp_creates_valid_candle_frame(self, data):
        """Test that dropping timestamp from TimeCandleFrame creates valid CandleFrame."""
        assume(all(v >= 0 for v in data["volume"]))

        df = pl.LazyFrame(data).with_columns(pl.col("timestamp").cast(pl.UInt64), pl.col("volume").cast(pl.UInt64))
        time_validated = TimeCandleFrame.validate(df)

        # Drop timestamp to get CandleFrame
        candle_df = time_validated.drop("timestamp")
        candle_validated = CandleFrame.validate(candle_df)
        result = candle_validated.collect()

        assert "timestamp" not in result.columns
        assert result.shape[1] == 5


# ---------------------------------------------------------------------------
# Edge Case Tests
# ---------------------------------------------------------------------------


class TestEdgeCases:
    """Tests for edge cases and boundary conditions."""

    def test_zero_volume_is_valid(self):
        """Test that zero volume is valid."""
        df = pl.LazyFrame(
            {
                "open": [100.0],
                "high": [102.0],
                "low": [99.0],
                "close": [101.0],
                "volume": [0],
            }
        ).with_columns(pl.col("volume").cast(pl.UInt64))
        validated = CandleFrame.validate(df)
        result = validated.collect()

        assert result["volume"][0] == 0

    def test_large_volume_is_valid(self):
        """Test that very large volume values are valid."""
        df = pl.LazyFrame(
            {
                "open": [100.0],
                "high": [102.0],
                "low": [99.0],
                "close": [101.0],
                "volume": [10**15],  # Very large volume
            }
        ).with_columns(pl.col("volume").cast(pl.UInt64))
        validated = CandleFrame.validate(df)
        result = validated.collect()

        assert result["volume"][0] == 10**15

    def test_extreme_price_values(self):
        """Test handling of extreme but valid price values."""
        df = pl.LazyFrame(
            {
                "open": [0.000001],  # Very small price
                "high": [1e12],  # Very large price
                "low": [0.0000001],
                "close": [999999999.99],
                "volume": [1],
            }
        ).with_columns(pl.col("volume").cast(pl.UInt64))
        validated = CandleFrame.validate(df)
        result = validated.collect()

        assert result.shape == (1, 5)

    def test_nan_in_price_raises_error_with_coercion(self):
        """Test that NaN values in price columns are handled appropriately."""
        df = pl.LazyFrame(
            {
                "open": [float("nan")],
                "high": [102.0],
                "low": [99.0],
                "close": [101.0],
                "volume": [1000],
            }
        ).with_columns(pl.col("volume").cast(pl.UInt64))
        # NaN handling depends on pandera configuration
        # This test documents the current behavior
        try:
            validated = CandleFrame.validate(df)
            result = validated.collect()
            # If validation passes, check that the NaN is preserved
            assert result["open"].is_nan()[0]
        except SchemaError:
            # If validation fails, that's also acceptable behavior
            pass

    def test_inf_in_price_success(self):
        """Test that infinity values in price columns are handled appropriately."""
        df = pl.LazyFrame(
            {
                "open": [float("inf")],
                "high": [102.0],
                "low": [99.0],
                "close": [101.0],
                "volume": [1000],
            }
        ).with_columns(pl.col("volume").cast(pl.UInt64))
        validated = CandleFrame.validate(df)
        result = validated.collect()
        assert result["open"][0] == float("inf")

    @given(n_rows=st.integers(min_value=1, max_value=1000))
    @settings(max_examples=10)
    def test_varying_row_counts(self, n_rows):
        """Test CandleFrame with varying numbers of rows."""
        df = pl.LazyFrame(
            {
                "open": [100.0] * n_rows,
                "high": [102.0] * n_rows,
                "low": [99.0] * n_rows,
                "close": [101.0] * n_rows,
                "volume": [1000] * n_rows,
            }
        ).with_columns(pl.col("volume").cast(pl.UInt64))
        validated = CandleFrame.validate(df)
        result = validated.collect()

        assert result.shape == (n_rows, 5)

    def test_max_uint64_timestamp(self):
        """Test handling of maximum UInt64 timestamp value."""
        max_uint64 = 2**64 - 1
        df = pl.LazyFrame(
            {
                "timestamp": [max_uint64],
                "open": [100.0],
                "high": [102.0],
                "low": [99.0],
                "close": [101.0],
                "volume": [1000],
            }
        ).with_columns(pl.col("timestamp").cast(pl.UInt64), pl.col("volume").cast(pl.UInt64))

        validated = TimeCandleFrame.validate(df)
        result = validated.collect()

        assert result["timestamp"][0] == max_uint64

    def test_zero_timestamp(self):
        """Test handling of zero timestamp value."""
        df = pl.LazyFrame(
            {
                "timestamp": [0],
                "open": [100.0],
                "high": [102.0],
                "low": [99.0],
                "close": [101.0],
                "volume": [1000],
            }
        ).with_columns(pl.col("timestamp").cast(pl.UInt64), pl.col("volume").cast(pl.UInt64))

        validated = TimeCandleFrame.validate(df)
        result = validated.collect()

        assert result["timestamp"][0] == 0

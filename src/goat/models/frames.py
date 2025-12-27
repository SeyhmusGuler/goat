import pandera.polars as pal
import polars as pl


class CandleFrame(pal.DataFrameModel):
    open: pl.Float64
    high: pl.Float64
    low: pl.Float64
    close: pl.Float64
    volume: pl.UInt64


class TimeCandleFrame(CandleFrame):
    timestamp: pl.UInt64


if __name__ == "__main__":
    df = CandleFrame.validate(
        pl.DataFrame(
            {
                "timestamp": [1672531200000, 1672531260000],
                "open": [100.0, 101.0],
                "high": [102.0, 103.0],
                "low": [99.0, 100.0],
                "close": [101.0, 102.0],
                "volume": [1000, 2000],
            }
        )
        .with_columns(
            timestamp=pl.col("timestamp").cast(pl.UInt64),
            volume=pl.col("volume").cast(pl.UInt64),
        )
        .lazy()
    )
    print(df.collect())

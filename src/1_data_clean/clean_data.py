"""Clean the course train/validation trips and build zone-time statistics."""

from __future__ import annotations

import argparse
from datetime import datetime
import json
from pathlib import Path

import pyarrow as pa
import pyarrow.compute as pc
import pyarrow.parquet as pq


ZONE_MIN = 1
ZONE_MAX = 263
MIN_DURATION_SECONDS = 30.0
MAX_DURATION_SECONDS = 4 * 60 * 60.0
MAX_DISTANCE_MILES = 100.0
MAX_FARE_AMOUNT = 500.0
MAX_TOTAL_AMOUNT = 1_000.0
MAX_SPEED_MPH = 80.0

REQUIRED_COLUMNS = (
    "tpep_pickup_datetime",
    "tpep_dropoff_datetime",
    "PULocationID",
    "DOLocationID",
    "trip_distance",
    "fare_amount",
    "total_amount",
)

DUPLICATE_KEY = (
    "tpep_pickup_datetime",
    "tpep_dropoff_datetime",
    "PULocationID",
    "DOLocationID",
    "trip_distance",
    "fare_amount",
    "total_amount",
)


def clean_table(table: pa.Table) -> tuple[pa.Table, dict[str, object]]:
    """Apply deterministic filters and append pickup-time features."""
    missing = sorted(set(REQUIRED_COLUMNS).difference(table.column_names))
    if missing:
        raise ValueError(f"missing required columns: {', '.join(missing)}")

    report: dict[str, object] = {"source_rows": table.num_rows}

    required_mask = pc.is_valid(table[REQUIRED_COLUMNS[0]])
    for column in REQUIRED_COLUMNS[1:]:
        required_mask = pc.and_(required_mask, pc.is_valid(table[column]))
    for column in ("trip_distance", "fare_amount", "total_amount"):
        required_mask = pc.and_(required_mask, pc.is_finite(table[column]))
    table, removed = _filter(table, required_mask)
    report["removed_missing_or_non_finite_required"] = removed

    before = table.num_rows
    table = _drop_duplicate_orders(table)
    report["removed_duplicates"] = before - table.num_rows

    zone_mask = _between(table["PULocationID"], ZONE_MIN, ZONE_MAX)
    zone_mask = pc.and_(
        zone_mask,
        _between(table["DOLocationID"], ZONE_MIN, ZONE_MAX),
    )
    table, removed = _filter(table, zone_mask)
    report["removed_invalid_zones"] = removed

    duration_seconds = _duration_seconds(table)
    duration_mask = pc.and_(
        pc.greater(duration_seconds, MIN_DURATION_SECONDS),
        pc.less_equal(duration_seconds, MAX_DURATION_SECONDS),
    )
    table, removed = _filter(table, duration_mask)
    report["removed_invalid_duration"] = removed

    distance_mask = pc.and_(
        pc.greater(table["trip_distance"], 0.0),
        pc.less_equal(table["trip_distance"], MAX_DISTANCE_MILES),
    )
    table, removed = _filter(table, distance_mask)
    report["removed_invalid_distance"] = removed

    fare_mask = _between(table["fare_amount"], 0.0, MAX_FARE_AMOUNT)
    fare_mask = pc.and_(
        fare_mask,
        _between(table["total_amount"], 0.0, MAX_TOTAL_AMOUNT),
    )
    table, removed = _filter(table, fare_mask)
    report["removed_invalid_fare"] = removed

    duration_seconds = _duration_seconds(table)
    speed_mph = pc.divide(
        pc.multiply(pc.cast(table["trip_distance"], pa.float64()), 3_600.0),
        duration_seconds,
    )
    speed_mask = pc.and_(
        pc.greater(speed_mph, 0.0),
        pc.less_equal(speed_mph, MAX_SPEED_MPH),
    )
    table, removed = _filter(table, speed_mask)
    report["removed_invalid_speed"] = removed

    table = _append_features(table)
    report["output_rows"] = table.num_rows
    report.update(_date_range(table))
    return table, report


def build_zone_time_statistics(cleaned_train: pa.Table) -> pa.Table:
    """Aggregate cleaned training pickups by weekday, slot, and zone."""
    grouped = cleaned_train.group_by(
        ["PULocationID", "weekday", "time_slot"]
    ).aggregate(
        [
            ("total_amount", "count"),
            ("total_amount", "mean"),
        ]
    )
    grouped = grouped.rename_columns(
        [
            "pickup_location_id",
            "weekday",
            "time_slot",
            "pickup_count",
            "mean_total_amount",
        ]
    )
    grouped = grouped.set_column(
        0,
        "pickup_location_id",
        pc.cast(grouped["pickup_location_id"], pa.int64()),
    )
    grouped = grouped.set_column(
        1, "weekday", pc.cast(grouped["weekday"], pa.int64())
    )
    grouped = grouped.set_column(
        2, "time_slot", pc.cast(grouped["time_slot"], pa.int64())
    )
    grouped = grouped.set_column(
        3, "pickup_count", pc.cast(grouped["pickup_count"], pa.int64())
    )
    return grouped.sort_by(
        [
            ("weekday", "ascending"),
            ("time_slot", "ascending"),
            ("pickup_location_id", "ascending"),
        ]
    )


def run(
    train_input: Path,
    validation_input: Path,
    output_dir: Path,
) -> dict[str, object]:
    """Clean both partitions and write all Part 1 outputs."""
    output_dir.mkdir(parents=True, exist_ok=True)
    train_cleaned, train_report = clean_table(pq.read_table(train_input))
    validation_cleaned, validation_report = clean_table(
        pq.read_table(validation_input)
    )
    statistics = build_zone_time_statistics(train_cleaned)

    _write_parquet_atomic(train_cleaned, output_dir / "train_cleaned.parquet")
    _write_parquet_atomic(
        validation_cleaned,
        output_dir / "validation_cleaned.parquet",
    )
    _write_parquet_atomic(
        statistics,
        output_dir / "zone_time_statistics.parquet",
    )

    result = {
        "rules": {
            "zone_ids": "1..263",
            "duration_seconds": "(30, 14400]",
            "trip_distance_miles": "(0, 100]",
            "fare_amount": "[0, 500]",
            "total_amount": "[0, 1000]",
            "average_speed_mph": "(0, 80]",
        },
        "train": train_report,
        "validation": validation_report,
        "zone_time_statistics": {
            "rows": statistics.num_rows,
            "pickup_count_sum": pc.sum(statistics["pickup_count"]).as_py(),
        },
    }
    print(json.dumps(result, indent=2))
    return result


def _drop_duplicate_orders(table: pa.Table) -> pa.Table:
    row_ids = pa.array(range(table.num_rows), type=pa.int64())
    indexed = table.append_column("__row_id", row_ids)
    first_rows = indexed.group_by(list(DUPLICATE_KEY)).aggregate(
        [("__row_id", "min")]
    )["__row_id_min"]
    first_rows = pc.take(first_rows, pc.sort_indices(first_rows))
    return table.take(first_rows)


def _append_features(table: pa.Table) -> pa.Table:
    pickup = table["tpep_pickup_datetime"]
    duration_seconds = _duration_seconds(table)
    weekday = pc.cast(
        pc.day_of_week(pickup, count_from_zero=True, week_start=1),
        pa.int8(),
    )
    hour = pc.cast(pc.hour(pickup), pa.int16())
    minute = pc.cast(pc.minute(pickup), pa.int16())
    half_hour = pc.cast(
        pc.floor(pc.divide(pc.cast(minute, pa.float64()), 30.0)),
        pa.int16(),
    )
    time_slot = pc.cast(pc.add(pc.multiply(hour, 2), half_hour), pa.int8())
    speed_mph = pc.divide(
        pc.multiply(pc.cast(table["trip_distance"], pa.float64()), 3_600.0),
        duration_seconds,
    )

    features = (
        ("pickup_date", pc.cast(pickup, pa.date32())),
        (
            "pickup_slot_start",
            pc.floor_temporal(pickup, multiple=30, unit="minute"),
        ),
        ("weekday", weekday),
        ("time_slot", time_slot),
        ("is_workday", pc.less(weekday, 5)),
        (
            "trip_duration",
            pc.divide(duration_seconds, 60.0),
        ),
        ("average_speed_mph", speed_mph),
    )
    for name, values in features:
        if name in table.column_names:
            table = table.set_column(table.column_names.index(name), name, values)
        else:
            table = table.append_column(name, values)
    return table


def _duration_seconds(table: pa.Table) -> pa.ChunkedArray:
    duration_us = pc.cast(
        pc.subtract(
            table["tpep_dropoff_datetime"],
            table["tpep_pickup_datetime"],
        ),
        pa.int64(),
    )
    return pc.divide(pc.cast(duration_us, pa.float64()), 1_000_000.0)


def _between(values: pa.ChunkedArray, lower: float, upper: float) -> pa.Array:
    return pc.and_(pc.greater_equal(values, lower), pc.less_equal(values, upper))


def _filter(table: pa.Table, mask: pa.Array) -> tuple[pa.Table, int]:
    before = table.num_rows
    filtered = table.filter(pc.fill_null(mask, False))
    return filtered, before - filtered.num_rows


def _date_range(table: pa.Table) -> dict[str, str | None]:
    def value(column: str, function: object) -> str | None:
        scalar = function(table[column])  # type: ignore[operator]
        result = scalar.as_py()
        return result.isoformat(sep=" ") if isinstance(result, datetime) else None

    return {
        "pickup_time_min": value("tpep_pickup_datetime", pc.min),
        "pickup_time_max": value("tpep_pickup_datetime", pc.max),
        "dropoff_time_min": value("tpep_dropoff_datetime", pc.min),
        "dropoff_time_max": value("tpep_dropoff_datetime", pc.max),
    }


def _write_parquet_atomic(table: pa.Table, output_path: Path) -> None:
    temporary = output_path.with_name(f".{output_path.name}.tmp")
    pq.write_table(table, temporary, compression="zstd")
    temporary.replace(output_path)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--train-input",
        type=Path,
        default=Path("data/processed/train_uncleaned.parquet"),
    )
    parser.add_argument(
        "--validation-input",
        type=Path,
        default=Path("data/processed/validation_uncleaned.parquet"),
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("data/processed"),
    )
    args = parser.parse_args()
    run(args.train_input, args.validation_input, args.output_dir)


if __name__ == "__main__":
    main()

"""Baseline 1 strategy: rank zones by historical next-slot pickup demand."""

from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path

import pyarrow.parquet as pq


ZONE_COUNT = 263
PROJECT_ROOT = Path(__file__).resolve().parents[2]
STATISTICS_PATH = PROJECT_ROOT / "data/processed/zone_time_statistics.parquet"


def recommend(
    current_datetime: datetime,
    current_location_id: int,
) -> list[int]:
    """Return the Top-3 LocationIDs for one simulator state."""
    if not isinstance(current_datetime, datetime):
        raise TypeError("current_datetime must be a datetime")
    if not 1 <= current_location_id <= ZONE_COUNT:
        raise ValueError("current_location_id must be in 1..263")

    target_time = _next_half_hour(current_datetime)
    slot = target_time.hour * 2 + target_time.minute // 30

    # TODO 1: Build the 263 demand scores for target_time.weekday() and slot.
    # The score of a zone is its historical pickup_count in the next slot.
    scores: list[float] = []

    # TODO 2: Implement Top-3 selection in descending score order.
    # Break ties by choosing the smaller LocationID first.
    raise NotImplementedError("complete Baseline 1 scoring and Top-3 selection")


def _load_pickup_counts() -> list[list[list[float]]]:
    """Load the provided weekday x slot x zone pickup-count table once."""
    counts = [[[0.0] * ZONE_COUNT for _ in range(48)] for _ in range(7)]
    for row in pq.read_table(
        STATISTICS_PATH,
        columns=["pickup_location_id", "weekday", "time_slot", "pickup_count"],
    ).to_pylist():
        location_id = int(row["pickup_location_id"])
        weekday = int(row["weekday"])
        time_slot = int(row["time_slot"])
        if 1 <= location_id <= ZONE_COUNT:
            counts[weekday][time_slot][location_id - 1] = float(
                row["pickup_count"]
            )
    return counts


def _next_half_hour(value: datetime) -> datetime:
    slot_start = value.replace(
        minute=(value.minute // 30) * 30,
        second=0,
        microsecond=0,
    )
    return slot_start + timedelta(minutes=30)


# Read the statistics once when the strategy file is loaded.
counts = _load_pickup_counts()

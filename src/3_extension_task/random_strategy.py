"""Reproducible random-policy lower bound."""

from datetime import datetime
import random


ZONE_COUNT = 263
_RNG = random.Random(20230717)


def recommend(current_datetime: datetime, current_location_id: int) -> list[int]:
    if not isinstance(current_datetime, datetime):
        raise TypeError("current_datetime must be a datetime")
    if not 1 <= current_location_id <= ZONE_COUNT:
        raise ValueError("current_location_id must be in 1..263")
    return _RNG.sample(range(1, ZONE_COUNT + 1), 3)

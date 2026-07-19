"""Shared train-only models for the Part 3 planning strategies."""

from __future__ import annotations

import csv
from datetime import datetime
from functools import lru_cache
import math
from pathlib import Path

import numpy as np
import pyarrow.parquet as pq


ZONE_COUNT = 263
WEEK_SLOTS = 7 * 48
DAYS_PER_WEEKDAY = np.array([4, 4, 3, 3, 3, 3, 4])
DEMAND_HALF_SATURATION = 40.0
DISCOUNT = 0.96
FUTURE_WEIGHT = 0.03
PROJECT_ROOT = Path(__file__).resolve().parents[2]
STATISTICS_PATH = PROJECT_ROOT / "data/processed/zone_time_statistics.parquet"
TRAVEL_TIME_PATH = PROJECT_ROOT / "data/processed/travel_time_matrix_dijkstra.csv"


def recommend_expected(current_datetime: datetime, current_location_id: int) -> list[int]:
    """Rank destinations by expected pickup fare per relocation slot."""
    slot, origin = _validate(current_datetime, current_location_id)
    return _top3(_one_step_scores(slot, origin))


def recommend_dp(current_datetime: datetime, current_location_id: int) -> list[int]:
    """Use an exact two-decision Bellman lookahead."""
    slot, origin = _validate(current_datetime, current_location_id)
    return _top3(_lookahead_scores(slot, origin, depth=2, beam_width=ZONE_COUNT))


def recommend_beam(current_datetime: datetime, current_location_id: int) -> list[int]:
    """Use four-decision lookahead and retain eight actions per later state."""
    slot, origin = _validate(current_datetime, current_location_id)
    return _top3(_lookahead_scores(slot, origin, depth=4, beam_width=8))


def recommend_hybrid(current_datetime: datetime, current_location_id: int) -> list[int]:
    """Keep Baseline 2 utility and add a conservative three-step value bonus."""
    slot, origin = _validate(current_datetime, current_location_id)
    return _top3(_hybrid_scores(slot, origin, depth=3, beam_width=8))


def recommend_two_step_rate(
    current_datetime: datetime, current_location_id: int
) -> list[int]:
    """Maximize two-attempt expected fare per expected relocation slot."""
    slot, origin = _validate(current_datetime, current_location_id)
    probability, fare, travel_slots, _, _ = _model()
    steps = travel_slots[origin]
    destinations = np.arange(ZONE_COUNT)
    arrival = (slot + steps) % WEEK_SLOTS
    reachable = steps <= WEEK_SLOTS
    first_probability = probability[arrival, destinations]
    first_reward = first_probability * fare[arrival, destinations]
    scores = np.full(ZONE_COUNT, -np.inf)
    for destination in np.flatnonzero(reachable):
        second_reward, second_steps = _best_followup(
            int(arrival[destination]), int(destination)
        )
        failure = 1.0 - first_probability[destination]
        scores[destination] = (
            first_reward[destination] + failure * second_reward
        ) / (steps[destination] + failure * second_steps)
    return _top3(scores)


def _validate(value: datetime, location_id: int) -> tuple[int, int]:
    if not isinstance(value, datetime):
        raise TypeError("current_datetime must be a datetime")
    if not 1 <= location_id <= ZONE_COUNT:
        raise ValueError("current_location_id must be in 1..263")
    return value.weekday() * 48 + value.hour * 2 + value.minute // 30, location_id - 1


def _top3(scores: np.ndarray) -> list[int]:
    return (np.lexsort((np.arange(ZONE_COUNT), -scores))[:3] + 1).tolist()


def _one_step_scores(slot: int, origin: int) -> np.ndarray:
    probability, fare, travel_slots, _, _ = _model()
    steps = travel_slots[origin]
    reachable = steps <= WEEK_SLOTS
    destinations = np.arange(ZONE_COUNT)
    arrival = (slot + steps) % WEEK_SLOTS
    scores = np.full(ZONE_COUNT, -np.inf)
    scores[reachable] = (
        probability[arrival[reachable], destinations[reachable]]
        * fare[arrival[reachable], destinations[reachable]]
        / steps[reachable]
    )
    return scores


@lru_cache(maxsize=None)
def _best_followup(slot: int, origin: int) -> tuple[float, int]:
    probability, fare, travel_slots, _, _ = _model()
    scores = _one_step_scores(slot, origin)
    destination = int(np.argmax(scores))
    steps = int(travel_slots[origin, destination])
    arrival = (slot + steps) % WEEK_SLOTS
    reward = probability[arrival, destination] * fare[arrival, destination]
    return float(reward), steps


def _lookahead_scores(slot: int, origin: int, depth: int, beam_width: int) -> np.ndarray:
    probability, _, travel_slots, _, _ = _model()
    scores = _one_step_scores(slot, origin)
    steps = travel_slots[origin]
    for destination in np.flatnonzero(np.isfinite(scores)):
        arrival = (slot + steps[destination]) % WEEK_SLOTS
        failure = 1.0 - probability[arrival, destination]
        scores[destination] += (
            failure
            * DISCOUNT ** steps[destination]
            * _state_value(arrival, destination, depth - 1, beam_width)
        )
    return scores


@lru_cache(maxsize=None)
def _state_value(slot: int, origin: int, depth: int, beam_width: int) -> float:
    scores = _one_step_scores(slot, origin)
    if depth == 1:
        return float(np.max(scores))
    candidates = np.argsort(-scores, kind="stable")[:beam_width]
    probability, _, travel_slots, _, _ = _model()
    best = 0.0
    for destination in candidates:
        if not math.isfinite(scores[destination]):
            continue
        steps = int(travel_slots[origin, destination])
        arrival = (slot + steps) % WEEK_SLOTS
        failure = 1.0 - probability[arrival, destination]
        value = scores[destination] + failure * DISCOUNT ** steps * _state_value(
            arrival, int(destination), depth - 1, beam_width
        )
        best = max(best, value)
    return best


def _baseline_scores(slot: int, origin: int) -> np.ndarray:
    _, fare, _, demand, travel_minutes = _model()
    target = (slot + 1) % WEEK_SLOTS
    scores = demand[target] * fare[target] / (travel_minutes[origin] + 1.0)
    return np.where(np.isfinite(scores), scores, 0.0)


def _hybrid_scores(slot: int, origin: int, depth: int, beam_width: int) -> np.ndarray:
    probability, _, travel_slots, _, _ = _model()
    scores = _baseline_scores(slot, origin)
    maximum = float(np.max(scores))
    if maximum > 0.0:
        scores = scores / maximum
    for destination in np.flatnonzero(travel_slots[origin] <= WEEK_SLOTS):
        steps = int(travel_slots[origin, destination])
        arrival = (slot + steps) % WEEK_SLOTS
        failure = 1.0 - probability[arrival, destination]
        scores[destination] += FUTURE_WEIGHT * failure * DISCOUNT ** steps * _hybrid_value(
            arrival, int(destination), depth - 1, beam_width
        )
    return scores


@lru_cache(maxsize=None)
def _hybrid_value(slot: int, origin: int, depth: int, beam_width: int) -> float:
    scores = _baseline_scores(slot, origin)
    maximum = float(np.max(scores))
    if maximum > 0.0:
        scores = scores / maximum
    if depth == 1:
        return float(np.max(scores))
    candidates = np.argsort(-scores, kind="stable")[:beam_width]
    probability, _, travel_slots, _, _ = _model()
    best = 0.0
    for destination in candidates:
        steps = int(travel_slots[origin, destination])
        if steps > WEEK_SLOTS:
            continue
        arrival = (slot + steps) % WEEK_SLOTS
        failure = 1.0 - probability[arrival, destination]
        value = scores[destination] + FUTURE_WEIGHT * failure * DISCOUNT ** steps * _hybrid_value(
            arrival, int(destination), depth - 1, beam_width
        )
        best = max(best, value)
    return best


@lru_cache(maxsize=1)
def _model() -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    demand = np.zeros((WEEK_SLOTS, ZONE_COUNT))
    fare = np.zeros_like(demand)
    columns = [
        "pickup_location_id", "weekday", "time_slot", "pickup_count",
        "mean_total_amount",
    ]
    for row in pq.read_table(STATISTICS_PATH, columns=columns).to_pylist():
        weekday = int(row["weekday"])
        index = weekday * 48 + int(row["time_slot"])
        zone = int(row["pickup_location_id"]) - 1
        demand[index, zone] = float(row["pickup_count"]) / DAYS_PER_WEEKDAY[weekday]
        fare[index, zone] = max(0.0, float(row["mean_total_amount"] or 0.0))

    with TRAVEL_TIME_PATH.open(encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.reader(handle))[1:]
    travel_minutes = np.array([[float(value) for value in row[1:]] for row in rows])
    travel_slots = np.full((ZONE_COUNT, ZONE_COUNT), WEEK_SLOTS + 1, dtype=np.int16)
    finite = np.isfinite(travel_minutes)
    travel_slots[finite] = np.maximum(
        1, np.ceil(travel_minutes[finite] / 30.0)
    ).astype(np.int16)
    probability = demand / (demand + DEMAND_HALF_SATURATION)
    return probability, fare, travel_slots, demand, travel_minutes

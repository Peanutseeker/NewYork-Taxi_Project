"""Evaluate one recommendation strategy with the month-long simulator."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from eval.simultor import (
    load_strategy,
    load_trip_market,
    load_travel_time_matrix,
    simulate_many,
)


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_TRIPS = PROJECT_ROOT / "data/raw/yellow_tripdata_2023-02.parquet"
DEFAULT_TRAVEL_TIMES = (
    PROJECT_ROOT / "src/eval/travel_time_matrix.csv"
)
DEFAULT_OUTPUT = PROJECT_ROOT / "tmp/evaluation.json"
SIMULATION_RUNS = 200
SIMULATION_BASE_SEED = 20230717


def evaluate_strategy(
    *,
    strategy_path: Path,
    trips_path: Path = DEFAULT_TRIPS,
    travel_times_path: Path = DEFAULT_TRAVEL_TIMES,
    output_path: Path = DEFAULT_OUTPUT,
) -> dict[str, object]:
    """Run 200 reproducible month-long simulations for one strategy."""
    simulator_result = simulate_many(
        strategy=load_strategy(strategy_path),
        market=load_trip_market(trips_path),
        travel_times=load_travel_time_matrix(travel_times_path),
        runs=SIMULATION_RUNS,
        base_seed=SIMULATION_BASE_SEED,
    )
    result: dict[str, object] = {
        "simulator_score": simulator_result["score"],
        "average_total_income": simulator_result["average_total_income"],
        "average_recommend_time_ms": simulator_result[
            "average_recommend_time_ms"
        ],
        "simulator_evaluation": simulator_result,
        "strategy_file": str(strategy_path),
        "travel_time_file": str(travel_times_path),
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--strategy", type=Path, required=True)
    parser.add_argument("--trips", type=Path, default=DEFAULT_TRIPS)
    parser.add_argument("--travel-times", type=Path, default=DEFAULT_TRAVEL_TIMES)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    result = evaluate_strategy(
        strategy_path=args.strategy,
        trips_path=args.trips,
        travel_times_path=args.travel_times,
        output_path=args.output,
    )
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()

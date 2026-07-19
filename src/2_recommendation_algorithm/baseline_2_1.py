"""Build the 263 x 263 directed shortest-travel-time matrix for Baseline 2."""

from __future__ import annotations

import argparse
import csv
import math
from pathlib import Path

import numpy as np
import pyarrow.parquet as pq
from scipy.sparse import csr_matrix
from scipy.sparse.csgraph import dijkstra


ZONE_COUNT = 263
PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_TRAIN_PATH = PROJECT_ROOT / "data/processed/train_cleaned.parquet"
DEFAULT_OUTPUT_PATH = (
    PROJECT_ROOT / "data/processed/travel_time_matrix_dijkstra.csv"
)


def build_matrix(train_path: Path, output_path: Path) -> None:
    """Aggregate OD edges, run all-source Dijkstra, and write a CSV matrix."""
    # TODO 1: Read PULocationID, DOLocationID, and trip_duration from train_path.
    # TODO 2: Use the mean duration of each directed OD pair as its edge weight.
    # TODO 3: Build a directed 263-node graph and run all-source Dijkstra.
    # Unreachable pairs must remain inf. Library graph/Dijkstra functions are allowed.
    matrix: np.ndarray
    raise NotImplementedError("build the directed shortest-time matrix")

    # Remove the NotImplementedError after matrix has been computed.
    _write_matrix(output_path, matrix)


def _write_matrix(output_path: Path, matrix: np.ndarray) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle, lineterminator="\n")
        writer.writerow(["origin_location_id", *range(1, ZONE_COUNT + 1)])
        for origin, distances in enumerate(matrix, start=1):
            writer.writerow(
                [
                    origin,
                    *(
                        "inf" if math.isinf(value) else f"{value:.6f}"
                        for value in distances
                    ),
                ]
            )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build the directed Dijkstra travel-time matrix."
    )
    parser.add_argument("--train", type=Path, default=DEFAULT_TRAIN_PATH)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT_PATH)
    args = parser.parse_args()
    build_matrix(args.train, args.output)
    print(f"wrote {ZONE_COUNT} x {ZONE_COUNT} matrix to {args.output}")


if __name__ == "__main__":
    main()

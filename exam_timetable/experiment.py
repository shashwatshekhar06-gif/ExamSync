"""Experiment harness: runs all three algorithms on the same problem sizes
(10, 30, 60 exams) with identical constraints, per the proposal's
experiment plan, and writes a comparison table + plots.
"""

import csv
import os
import random
from typing import Dict, List

from .algorithms import genetic_algorithm, hill_climbing, simulated_annealing
from .generator import generate_instance
from .palette import ALGORITHM_COLORS

PROBLEM_SIZES = [10, 30, 60]

ALGORITHMS = {
    "Hill-Climbing": lambda instance, rng: hill_climbing.run(
        instance, max_iters=100, rng=rng
    ),
    "Simulated Annealing": lambda instance, rng: simulated_annealing.run(
        instance, max_iters=5000, rng=rng
    ),
    "Genetic Algorithm": lambda instance, rng: genetic_algorithm.run(instance, rng=rng),
}


def run_experiment(seed: int = 42, results_dir: str = "results") -> List[Dict]:
    os.makedirs(results_dir, exist_ok=True)
    rows = []

    for size in PROBLEM_SIZES:
        instance = generate_instance(size, seed=seed)
        for name, algo in ALGORITHMS.items():
            rng = random.Random(seed)
            result = algo(instance, rng)
            row = {
                "problem_size": size,
                "algorithm": name,
                "iterations": result.iterations,
                "final_hard": result.cost.hard,
                "final_soft": result.cost.soft,
                "final_cost": result.cost.total,
                "elapsed_seconds": round(result.elapsed_seconds, 3),
            }
            rows.append(row)
            print(
                f"[{size} exams] {name}: cost={row['final_cost']} "
                f"(hard={row['final_hard']}, soft={row['final_soft']}) "
                f"iters={row['iterations']} time={row['elapsed_seconds']}s"
            )

    _write_csv(rows, results_dir)
    _write_plots(rows, results_dir)
    return rows


def _write_csv(rows: List[Dict], results_dir: str) -> None:
    csv_path = os.path.join(results_dir, "comparison.csv")
    with open(csv_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
    print(f"Wrote {csv_path}")


def _write_plots(rows: List[Dict], results_dir: str) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    plots_dir = os.path.join(results_dir, "plots")
    os.makedirs(plots_dir, exist_ok=True)

    algorithms = sorted({r["algorithm"] for r in rows})
    metrics = [
        ("final_cost", "Final cost (lower is better)"),
        ("iterations", "Iterations / generations used"),
        ("elapsed_seconds", "Wall-clock time (s)"),
    ]

    for metric_key, title in metrics:
        plt.figure()
        for algo in algorithms:
            sizes = sorted({r["problem_size"] for r in rows if r["algorithm"] == algo})
            values = [
                next(
                    r[metric_key]
                    for r in rows
                    if r["algorithm"] == algo and r["problem_size"] == size
                )
                for size in sizes
            ]
            plt.plot(sizes, values, marker="o", label=algo, color=ALGORITHM_COLORS.get(algo))
        plt.xlabel("Problem size (number of exams)")
        plt.ylabel(title)
        plt.title(f"{title} vs problem size")
        plt.legend()
        plt.tight_layout()
        out_path = os.path.join(plots_dir, f"{metric_key}.png")
        plt.savefig(out_path)
        plt.close()
        print(f"Wrote {out_path}")

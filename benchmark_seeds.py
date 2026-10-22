"""Multi-seed benchmark: mean +/- std for every algorithm.

One run on one instance can't show that one algorithm beats another, so this
repeats every (problem size, algorithm) pair over several seeds. Each seed
changes BOTH the generated problem instance and the algorithm's random
generator, so the numbers reflect "typical" behaviour, not one lucky draw.

    python benchmark_seeds.py                          # sizes 10 30 60, 5 seeds
    python benchmark_seeds.py --sizes 10 30 --seeds 3
    python benchmark_seeds.py --workers 4              # run jobs in parallel

Writes results/benchmark_seeds_raw.csv (every run) and
results/benchmark_seeds.csv (mean/std summary).

"GA (no local search)" is the plain GA (local_search_steps=0), included so
you can show how much of the GA's result comes from the local-search step.
"""

import argparse
import csv
import os
import random
import statistics
from concurrent.futures import ProcessPoolExecutor

from exam_timetable.algorithms import genetic_algorithm, hill_climbing, simulated_annealing
from exam_timetable.generator import generate_instance

ALGORITHMS = {
    "Hill-Climbing": (hill_climbing, {"max_iters": 100}),
    "Simulated Annealing": (simulated_annealing, {"max_iters": 5000}),
    "GA (no local search)": (genetic_algorithm, {"local_search_steps": 0}),
    "Genetic Algorithm": (genetic_algorithm, {}),
}


def _job(args):
    size, seed, name = args
    module, kwargs = ALGORITHMS[name]
    instance = generate_instance(size, seed=seed)
    result = module.run(instance, rng=random.Random(seed), **kwargs)
    return {
        "size": size,
        "seed": seed,
        "algorithm": name,
        "hard": result.cost.hard,
        "soft": result.cost.soft,
        "cost": result.cost.total,
        "seconds": round(result.elapsed_seconds, 2),
    }


def _fmt(values):
    mean = statistics.mean(values)
    std = statistics.stdev(values) if len(values) > 1 else 0.0
    return mean, std


def _summarise(rows):
    # Which algorithm(s) had the lowest cost on each (size, seed) instance.
    lowest = {}
    for r in rows:
        key = (r["size"], r["seed"])
        lowest[key] = min(lowest.get(key, r["cost"]), r["cost"])

    summary = []
    for size in sorted({r["size"] for r in rows}):
        for name in ALGORITHMS:
            mine = [r for r in rows if r["size"] == size and r["algorithm"] == name]
            if not mine:
                continue
            cost_mean, cost_std = _fmt([r["cost"] for r in mine])
            summary.append(
                {
                    "size": size,
                    "algorithm": name,
                    "runs": len(mine),
                    "cost_mean": round(cost_mean, 1),
                    "cost_std": round(cost_std, 1),
                    "hard_mean": round(statistics.mean(r["hard"] for r in mine), 2),
                    "soft_mean": round(statistics.mean(r["soft"] for r in mine), 1),
                    "feasible_runs": sum(1 for r in mine if r["hard"] == 0),
                    "lowest_cost_runs": sum(
                        1 for r in mine if r["cost"] == lowest[(size, r["seed"])]
                    ),
                    "seconds_mean": round(statistics.mean(r["seconds"] for r in mine), 1),
                }
            )
    return summary


def _write_csv(path, rows):
    with open(path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def main():
    parser = argparse.ArgumentParser(description="Multi-seed algorithm benchmark")
    parser.add_argument("--sizes", type=int, nargs="+", default=[10, 30, 60])
    parser.add_argument("--seeds", type=int, default=5, help="number of seeds")
    parser.add_argument("--first-seed", type=int, default=1)
    parser.add_argument("--workers", type=int, default=1, help="parallel processes")
    parser.add_argument("--results-dir", default="results")
    args = parser.parse_args()

    seeds = range(args.first_seed, args.first_seed + args.seeds)
    jobs = [
        (size, seed, name)
        for size in args.sizes
        for seed in seeds
        for name in ALGORITHMS
    ]
    print(f"{len(jobs)} runs: sizes={args.sizes}, seeds={list(seeds)}, workers={args.workers}")

    rows = []

    def record(row):
        rows.append(row)
        print(
            f"[{row['size']} exams, seed {row['seed']}] {row['algorithm']}: "
            f"cost={row['cost']} (hard={row['hard']}, soft={row['soft']}) {row['seconds']}s",
            flush=True,
        )

    if args.workers <= 1:
        for job in jobs:
            record(_job(job))
    else:
        with ProcessPoolExecutor(max_workers=args.workers) as pool:
            for row in pool.map(_job, jobs):
                record(row)

    summary = _summarise(rows)
    os.makedirs(args.results_dir, exist_ok=True)
    _write_csv(os.path.join(args.results_dir, "benchmark_seeds_raw.csv"), rows)
    _write_csv(os.path.join(args.results_dir, "benchmark_seeds.csv"), summary)

    print()
    print(f"{'size':>4}  {'algorithm':<21} {'cost (mean +/- std)':>20} {'hard':>5} {'feasible':>9} {'lowest':>7} {'time(s)':>8}")
    for s in summary:
        print(
            f"{s['size']:>4}  {s['algorithm']:<21} "
            f"{s['cost_mean']:>12.1f} +/- {s['cost_std']:<5.1f} "
            f"{s['hard_mean']:>5.2f} {s['feasible_runs']:>4}/{s['runs']:<4} "
            f"{s['lowest_cost_runs']:>3}/{s['runs']:<3} {s['seconds_mean']:>8.1f}"
        )
    print("\n'feasible' = runs ending with 0 hard violations; "
          "'lowest' = instances where that algorithm had the lowest cost (ties count for all).")


if __name__ == "__main__":
    main()

# Genetic Algorithm: memetic variant

`exam_timetable/algorithms/genetic_algorithm.py`. Same state, cost function
and operators as the other two algorithms; no external libraries.

## Design

Tournament selection, single-point crossover, per-gene mutation (rate
about 1 changed exam per child) and elitism, as in the plain GA. On top of
that, every child gets a short cost-guided **local search** (`refine`): each
step takes an exam that is in a hard violation (or a random one if there is
none) and moves it to its best (slot, room). Random crossover/mutation
explore; the local search exploits.

Defaults: population 10, 200 generations, 30 local-search steps per child,
plateau limit 100. A small population with a lot of local search per child
beat a large population with little of it at the same running time.
`local_search_steps=0` gives the plain GA back (ablation).

## Why it is fast

- `best_shift` computes the cost change of moving one exam to every
  (slot, room) from per-student slot counts and per-day period bitmasks,
  with no dictionary copies or sorting. It returns exactly the move that
  scanning `cost.delta_shift` over all pairs would (tested).
- The search state is updated in place after each move rather than rebuilt,
  and the child's cost is tracked from the move deltas rather than
  re-evaluated (tested against `cost.evaluate`).

## Benchmarks (default settings, 1 CPU core)

Total cost (hard x10 + soft), lower is better; mean over the seeds shown.

| Instance | Seeds | Hill-Climbing | Simulated Annealing | GA (this) |
|---|---|---|---|---|
| `data/sample/` (30 exams, 5x3 grid) | 42-44 | 163 | 165 | **157** |
| Synthetic, 30 exams | 1-3 | 204 | 210 | **182** |
| Synthetic, 60 exams | 1 | 473 | 590 | **464** |
| Old dense sample (432/435 pairs conflict; infeasible on 15 slots) | 42-43 | 856 | 847 | **790** |

GA runtime is about 20-30 s (HC 14-92 s, SA 4-10 s). On the sample and the
30-exam instances the GA reaches 0 hard violations on every seed; HC and SA
sometimes end with 1.

Caveats: few seeds per instance, and only one seed at 60 exams, so small
gaps (for example 464 vs 473) are within noise. The dense instance has a
floor near 790 because about 34 hard violations are unavoidable with 15
slots. Re-run `python benchmark_seeds.py` for more seeds.

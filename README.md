# Automated Exam Timetable Generator

AI course project (Module 3 — Local Search). Three algorithms — Hill-Climbing,
Simulated Annealing, and a Genetic Algorithm — solve the same exam-to-(time
slot, room) assignment problem, sharing one state representation and cost
function, so they can be compared fairly.

**Project direction:** this started as an algorithm-comparison exercise on
synthetic data (for Review 1) and is becoming a real tool: upload a
department's actual courses/enrollments/rooms as CSVs and get back a
generated timetable, plus a report of any unavoidable conflicts. See
[`CLAUDE.md`](CLAUDE.md) for full project context, current status, and the
open design decisions — read that first if you're picking this project up.

## What works today

- The solver core: state representation, cost function, and all three
  algorithms, running against **synthetically generated** problem instances.
- An experiment harness comparing all three algorithms across 10/30/60-exam
  synthetic instances, producing a CSV + plots.
- **CSV ingestion**: `exam_timetable/csv_loader.py` builds a
  `ProblemInstance` from three CSVs (`courses.csv`, `enrollments.csv`,
  `rooms.csv`) plus a days x periods grid. The format and validation rules
  are in [`docs/csv_schema.md`](docs/csv_schema.md); sample files are in
  [`data/sample/`](data/sample/).
- **A Streamlit frontend** (`app.py`): upload the CSVs (or use synthetic demo
  data), run one algorithm or compare all three, and get a timetable grid, a
  violations report, and CSV / .txt downloads.

## What's not built yet

- Non-uniform time-slot structures, pre-locked exams and room-type
  restrictions (stretch goals, tracked as GitHub Issues).
- Hyperparameter tuning and the results write-up for the report.

See [`CLAUDE.md`](CLAUDE.md) for the full status table.

## Roadmap / contributing

All remaining work is tracked as [GitHub Issues](../../issues) (#1-#16),
with dependencies between them noted on each issue. `CLAUDE.md` §10 keeps
a standing copy of the full issue list + dependency chain in case GitHub
itself isn't handy. If you're about to start work, read
[`CONTRIBUTING.md`](CONTRIBUTING.md) first for the branch/PR workflow.

## Structure

```
exam_timetable/
  models.py        Course, Room, TimeSlot, ProblemInstance
  generator.py      synthetic problem-instance generator (seeded, reproducible)
  state.py          the state: one (slot, room) pair per exam
  cost.py           the shared cost function (hard + soft violations),
                    plus incremental delta-cost functions Hill-Climbing uses
  operators.py      shift/swap moves, crossover, mutation, tournament selection
  result.py         common SearchResult type returned by all three algorithms
  algorithms/
    hill_climbing.py        exhaustive neighborhood, scored via delta-cost
    simulated_annealing.py  geometric cooling, Metropolis acceptance
    genetic_algorithm.py    memetic GA: selection + crossover + mutation + elitism +
                            local search per child (see docs/ga_memetic.md)
  experiment.py     runs all three algorithms on 10/30/60-exam instances,
                    writes results/comparison.csv and results/plots/*.png
  cli.py            argparse entry point
  csv_loader.py     CSV files -> ProblemInstance
  report.py         violations report for the frontend
  palette.py        one fixed colour per algorithm (plots + frontend)
app.py              Streamlit frontend
data/sample/        sample CSVs (schedulable on the default 5x3 grid)
docs/csv_schema.md  CSV input schema
scripts/            make_sample_data.py regenerates the sample enrollments
tests/              unit tests for cost function, state ops, generator,
                    algorithms, CSV loader, and the sample data
main.py             `python main.py ...`
```

## Setup

```
pip install -r requirements.txt
```

## Run

Solve a single synthetic instance with one algorithm:

```
python main.py solve --algorithm hc --exams 10
python main.py solve --algorithm sa --exams 30
python main.py solve --algorithm ga --exams 60
```

Run the full comparison (all three algorithms x 10/30/60 exams), producing
`results/comparison.csv` and `results/plots/*.png`:

```
python main.py experiment
```

Launch the frontend:

```
streamlit run app.py
```

Choose "Upload CSVs" and use the files in `data/sample/`, or pick the
synthetic demo data.

## Tests

```
pytest
```

## Notes

- Hard violations (student double-booked, room over capacity, two exams
  clashing in the same room/slot) are weighted 10; soft violations (a
  student with back-to-back exams, exams bunched onto one day) are weighted
  1. Both the weights and the algorithms' hyperparameters (iteration caps,
  cooling schedule, population size, mutation rate) are initial defaults —
  per the proposal, these get tuned during Review 2.
- No external optimization/metaheuristic libraries are used (no DEAP,
  PyGAD, or scipy.optimize) — the state, operators, and cost function are
  all implemented directly, per the proposal's declarations. matplotlib is
  used only for plotting results.

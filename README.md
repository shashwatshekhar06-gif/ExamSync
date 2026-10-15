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

## What's planned, not yet built

- **CSV ingestion**, to build a `ProblemInstance` from real data instead of
  `generator.py`'s synthetic one. Planned input files:
  - `courses.csv` — `course_id`, `course_name`
  - `enrollments.csv` — `student_id`, `course_id` (one row per student-course
    pair — this is what drives every student-side conflict check)
  - `rooms.csv` — `room_id`, `capacity`
  - exam period structure (days × periods/day) — likely a simple config
    rather than a file, unless slots turn out to be non-uniform
- **A frontend** to upload those CSVs, trigger a solve, and display the
  resulting timetable (plus a violations report, and optionally the
  three-algorithm comparison). Stack not yet decided — see `CLAUDE.md`.

None of this requires changing the algorithms, state, or cost function —
they already operate on `ProblemInstance`, which is agnostic to where the
data came from.

## Roadmap / contributing

All remaining work is tracked as [GitHub Issues](../../issues) (#1-#16),
with dependencies between them noted on each issue — e.g. the frontend MVP
is blocked on the CSV loader and the stack decision. `CLAUDE.md` §10 keeps
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
    genetic_algorithm.py    tournament selection + crossover + per-gene mutation + elitism
  experiment.py     runs all three algorithms on 10/30/60-exam instances,
                    writes results/comparison.csv and results/plots/*.png
  cli.py            argparse entry point
tests/              unit tests for cost function, state ops, generator, algorithms
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

## CSV Input Schema

The planned CSV input files use the following column headers.

### `courses.csv`

| Column | Description |
|---|---|
| `course_id` | Unique identifier for a course |
| `course_name` | Name of the course |

### `enrollments.csv`

| Column | Description |
|---|---|
| `student_id` | Identifier for a student |
| `course_id` | Identifier for a course the student is enrolled in |

Each row represents one student-course enrollment. A student enrolled in multiple courses appears in multiple rows.

### `rooms.csv`

| Column | Description |
|---|---|
| `room_id` | Identifier for an exam room |
| `capacity` | Maximum number of students the room can accommodate |

### Exam period configuration

The exam timetable uses a grid defined by the number of days and the number of periods per day. The CSV loader is not implemented yet, so this section documents the planned input format rather than a working import feature.

### Sample files

Example CSV files are available in the [`samples/`](samples/) directory.

These files document the planned schema and are provided for reference and testing when CSV ingestion is implemented.
# ExamSync — Automated Exam Timetable Generator

![Course](https://img.shields.io/badge/course-BCSE306L%20Artificial%20Intelligence-blue)
![Module](https://img.shields.io/badge/module-3%3A%20Local%20Search-orange)
![Language](https://img.shields.io/badge/language-Python-3776AB?logo=python&logoColor=white)
![Frontend](https://img.shields.io/badge/frontend-Streamlit-FF4B4B?logo=streamlit&logoColor=white)
![Plots](https://img.shields.io/badge/plots-matplotlib-11557c)
![Tests](https://img.shields.io/badge/tests-pytest-0A9EDC?logo=pytest&logoColor=white)

ExamSync is a university AI course project (BCSE306L, Module 3: Local Search). Three algorithms — Hill-Climbing, Simulated Annealing and a memetic Genetic Algorithm — solve the same exam-to-(time slot, room) assignment problem. They share one state representation, one cost function and one set of operators, so any difference in results comes from the search strategy and not from the setup. The Streamlit app lets you run them on your own department's data; the search algorithms are the academic focus.

## Links

| Resource | Link |
| --- | --- |
| Team repository | [shashwatshekhar06-gif/ExamSync](https://github.com/shashwatshekhar06-gif/ExamSync) |
| Fork | [Vignesh-P-C/ExamSync](https://github.com/Vignesh-P-C/ExamSync) |
| Hosted demo | None. Run it locally with `python -m streamlit run app.py` (see [Run](#run)) |

No credentials or private data are stored in this repository, and the sample data is synthetic.

---

## Problem Statement — ExamSync
### Automated Exam Timetable Generation with Local Search

### 1. Background

Every exam period, a department has to assign each exam a time slot and a room. The rules are simple to state and hard to satisfy together: rooms hold a limited number of students, one room cannot host two exams at once, and no student can sit two exams at the same time. Registrars usually do this by hand, in spreadsheets.

### 2. The Problem

**Clashes are easy to create and hard to find.** A student enrolled in four courses can be double-booked by a change that looks harmless elsewhere. Checking thousands of student–exam pairs by hand does not scale.

**A valid timetable is not necessarily a good one.** Even with no clashes, students can end up with back-to-back exams or several exams bunched onto one day.

**Fixes cause new problems.** Moving one exam to resolve a clash often creates another one somewhere else.

**Root cause:** the search space is huge and structured, and the quality of a solution can be measured with one number, which is exactly the setting local search is designed for.

### 3. Stakeholders

- **Exam coordinator** — generates a timetable and checks exactly what is still wrong with it
- **Students** — no double-booked exams, and a sensible spread of exams
- **Department administration** — a repeatable process that does not depend on one person's spreadsheet

### 4. Objectives

1. Represent a timetable as a **state** and score it with a single **cost function** (hard violations weighted 10, soft violations weighted 1)
2. Implement **Hill-Climbing, Simulated Annealing and a Genetic Algorithm** from scratch on that shared formulation
3. **Compare them fairly** on synthetic instances of 10, 30 and 60 exams, and on a realistic department-shaped sample
4. Accept **real data as CSV** (courses, enrollments, rooms) with no change to the algorithms
5. Report **specific remaining violations** (which student, which exams, which slot), not just a number
6. Verify the performance optimisations with **tests**, not by assumption

### 5. Scope

Single department, uniform-duration exam slots, rooms interchangeable except for capacity. Out of scope (tracked as stretch goals): pre-locked exams, variable exam durations, room-type restrictions, invigilator scheduling.

### 6. Why Local Search

A timetable assigns every exam one of `slots × rooms` positions, so the complete search space has `(slots × rooms)^exams` states. With 20 slots and 6 rooms that is about 10^125 states at 60 exams, so no exhaustive method is feasible. Local search never looks at the whole space: each step evaluates only the neighbourhood of the current timetable, so its cost grows polynomially with problem size. The trade-off is that it gives up the guarantee of finding the true optimum.

---

## Architecture

![Project pipeline: input files feed one ProblemInstance, three searches share one cost function, and results go to the report, the app and the experiment harness](docs/pipeline.png)

Real CSV files (`csv_loader.py`) and the seeded synthetic generator (`generator.py`) both produce the same `ProblemInstance`. This is the seam: nothing below it knows where the data came from, which is why adding CSV input and the frontend required no change to the algorithms, the cost function or the state. All three searches return the same `SearchResult`, so the report, the Streamlit app and the experiment harness consume any of them identically.

### How the Genetic Algorithm works

```mermaid
flowchart TD
    A["Random population (10 timetables)"] --> B["Evaluate every timetable"]
    B --> C{"Stop? cost = 0, 200 generations, or no improvement for 100 generations"}
    C -- yes --> Z["Return the best timetable found"]
    C -- no --> D["Copy the 2 best unchanged (elitism)"]
    D --> E["Pick two parents by tournament (3 contestants)"]
    E --> F["Single-point crossover"]
    F --> G["Mutate each exam with probability 1 / exams"]
    G --> H["Local search: up to 30 best-shift steps on exams in hard violations"]
    H --> I{"Next generation full?"}
    I -- no --> E
    I -- yes --> B
```

The local-search step on every child is what makes it memetic: crossover and mutation explore, the local search exploits. Details and benchmarks are in [`docs/ga_memetic.md`](docs/ga_memetic.md).

---

## AI Formulation

| Element | Definition |
| --- | --- |
| State | One timetable: every exam assigned a `(slot, room)` pair |
| Initial state | Random (Hill-Climbing, SA) or a random population (GA); violations are penalised by cost, not blocked |
| Operators | **Shift** (move one exam), **swap** (trade two exams); GA adds tournament selection, crossover, mutation, elitism and a per-child local search |
| Cost | `10 × hard + soft`. Hard: room over capacity, two exams in one room and slot, a student double-booked. Soft: bunching (several exams in one day) and back-to-back exams |
| Goal test | `cost == 0`; otherwise the best state found within the budget is returned |
| Termination | Hill-Climbing: local optimum or iteration cap. SA: temperature floor or iteration cap. GA: generation cap, cost 0, or a fitness plateau |

## The Three Algorithms

| Algorithm | How it searches | Notes |
| --- | --- | --- |
| Hill-Climbing | Scores every shift and swap each round and takes the best | Uses incremental **delta-cost**, so each candidate only touches the students of the moved exam(s). Stops at a local optimum |
| Simulated Annealing | One random shift/swap per step, accepted with probability `exp(−δ/T)` | Geometric cooling whose rate is derived from `max_iters`, so the schedule spans the configured budget |
| Genetic Algorithm (memetic) | Selection, crossover, per-gene mutation, elitism, then a short **local search on every child** | Without the local-search step the plain GA performed worst of all variants in the project's benchmark. See [`docs/ga_memetic.md`](docs/ga_memetic.md) |

## Results

Single seed (42), identical instance for all three algorithms, from `python main.py experiment`:

| Exams | Algorithm | Final cost | Hard violations |
| ---: | --- | ---: | ---: |
| 10 | Hill-Climbing / SA / GA | 34 / 34 / 34 | 0 / 0 / 0 |
| 30 | Hill-Climbing / SA / GA | 190 / 208 / **185** | 0 / 1 / 0 |
| 60 | Hill-Climbing / SA / GA | 479 / 525 / **426** | 1 / 8 / 1 |

On the realistic sample in `data/sample/` (30 courses, 300 students, 6 rooms, 5 days × 3 periods), seed 42 gives costs of 164 (Hill-Climbing, 0 hard), 166 (SA, 1 hard) and 158 (GA, 0 hard).

Notes and limits:

- Costs and iteration counts are reproducible from the seed; wall-clock times depend on the machine.
- A single seed can mislead. `python benchmark_seeds.py` repeats the comparison over several seeds, and the multi-seed tables and analysis are in the final report.
- Iteration counts are not comparable across algorithms. Hill-Climbing's rounds are each an exhaustive scan, so it needs few (24 on the sample), while SA always spends its full budget of 5000 cheap random moves.
- No algorithm guarantees cost 0. Always read the violations report before treating a timetable as final.
- Whether a conflict-free timetable exists depends on the input as well as the algorithm. The sample data needs at least 8 slots; a fully random enrolment would make nearly every pair of courses conflict and could not be scheduled on a small grid.
- Cost weights and the Hill-Climbing and SA parameters are initial defaults, not tuned values. Only the GA defaults were chosen from repeated runs and a multi-seed benchmark.

## Test Data

[`data/sample/`](data/sample/) holds a department-shaped sample (`courses.csv`, `enrollments.csv`, `rooms.csv`) that is schedulable on the default 5 × 3 grid. It is **synthetic**, regenerated by `scripts/make_sample_data.py`, and contains no real student data. The CSV format, validation rules and grid-size guidance are in [`docs/csv_schema.md`](docs/csv_schema.md).

## Structure

```
exam_timetable/
  models.py          Course, Room, TimeSlot, ProblemInstance
  generator.py       seeded synthetic problem-instance generator
  state.py           the state: one (slot, room) pair per exam
  cost.py            shared cost function + incremental delta-cost functions
  operators.py       shift/swap moves, crossover, mutation, tournament selection
  result.py          common SearchResult type returned by all three algorithms
  algorithms/
    hill_climbing.py        exhaustive neighbourhood, scored via delta-cost
    simulated_annealing.py  geometric cooling, Metropolis acceptance
    genetic_algorithm.py    memetic GA (see docs/ga_memetic.md)
  experiment.py      10/30/60-exam comparison -> results/comparison.csv + plots
  csv_loader.py      CSV files -> ProblemInstance
  report.py          per-violation report for the frontend
  palette.py         one fixed colour per algorithm
  cli.py             argparse entry point
app.py               Streamlit frontend
main.py              command-line entry point
benchmark_seeds.py   multi-seed benchmark
data/sample/         sample CSVs
docs/                csv_schema.md, ga_memetic.md, pipeline.png
scripts/             make_sample_data.py
tests/               cost, delta-cost, state, generator, algorithms,
                     CSV loader, memetic GA and sample-data tests (80 tests)
```

## Setup

```
python -m pip install -r requirements.txt
```

A virtual environment is optional (`python -m venv venv`, then activate it). The commands below use `python -m` so they also work when pip's `Scripts` folder is not on your PATH.

## Run

Solve one synthetic instance with one algorithm:

```
python main.py solve --algorithm hc --exams 10
python main.py solve --algorithm sa --exams 30
python main.py solve --algorithm ga --exams 60
```

Run the full comparison (all three algorithms × 10/30/60 exams); this writes `results/comparison.csv` and `results/plots/*.png`:

```
python main.py experiment
```

Launch the frontend, then choose **Upload CSVs** (use the files in `data/sample/`) or the synthetic demo data:

```
python -m streamlit run app.py
```

Choose a grid with enough slots for your data, or hard violations are unavoidable whatever the algorithm:

| Data | Days × periods |
| --- | --- |
| `data/sample/` CSVs | 5 × 3 (the default; the sample needs 8 slots) |
| Synthetic demo, 150 students | 5 × 4 (needs 19 slots) |
| Synthetic demo, 300 students | at least 6 × 5 (needs 29 slots) |

Hill-Climbing is the slowest at larger sizes (about a minute at 60 exams); lower its iteration cap in the app's Advanced settings for a quicker, rougher answer.

### Troubleshooting

- **`streamlit` or `pytest` is not recognised** (Windows): pip's `Scripts` folder is not on your PATH. Run them through Python instead: `python -m streamlit run app.py`, `python -m pytest`.
- **A virtual environment will not activate** in PowerShell: run `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` once, then activate it again.

## Tests

```
python -m pytest
```

The 80 tests cover the cost function, the delta-cost functions (checked against full re-evaluation), state operations, the generator, all three algorithms, the CSV loader, the memetic GA and the sample data.

## Team

| Member | Registration no. | Role |
| --- | --- | --- |
| Shashwat Shekhar | 24BCE2488 | Hill-Climbing lead; shared state and cost function |
| Suraj Doolipet | 24BCE2264 | Simulated Annealing lead |
| Vignesh P C | 24BCE0695 | Genetic Algorithm and experiment lead |

All three contributed to the CSV-ingestion layer and the frontend.

## Generative-AI Assistance

Claude (Anthropic) was used as an AI assistance tool to support the team with the algorithms, to diagnose and fix the Simulated Annealing cooling-schedule bug and the Genetic Algorithm mutation bug, to assist with the delta-cost optimisation, to build the CSV-ingestion layer and the web frontend, to write the test suite, and to draft and edit the final report. The Review 1 proposal and problem formulation were written without AI assistance, as declared at that stage, and that plan changed during implementation. The full and authoritative disclosure is Section 7.2 of the final report. See [`CLAUDE.md`](CLAUDE.md) for the project context used with the assistant.

## Contributing

Remaining work is tracked as GitHub Issues. Read [`CONTRIBUTING.md`](CONTRIBUTING.md) for the branch and pull-request workflow before starting.

## References

1. S. Russell and P. Norvig, *Artificial Intelligence: A Modern Approach*, 4th ed.
2. S. Kirkpatrick, C. D. Gelatt and M. P. Vecchi, "Optimization by Simulated Annealing," *Science*, 220(4598), 1983.
3. J. H. Holland, *Adaptation in Natural and Artificial Systems*, 1975.
4. P. Moscato, "On Evolution, Search, Optimization, Genetic Algorithms and Martial Arts: Towards Memetic Algorithms," Caltech Concurrent Computation Program, Report 826, 1989.

No external optimisation or metaheuristic library is used; matplotlib is used only for plotting and Streamlit only for the frontend.
# CLAUDE.md — Project Context for AI Collaborators

This file exists so a Claude session with no prior history on this project
(e.g. a teammate's session) can pick up work here without re-deriving
context from scratch. Read this fully before making changes. It is kept
up to date as the project evolves — if you change something that makes a
section below stale, update that section in the same session.

---

## 1. What this project is

**Automated Exam Timetable Generator** — a college AI course project
(Module 3: Local Search). Three local-search algorithms — Hill-Climbing,
Simulated Annealing, and a Genetic Algorithm — each independently solve
the same exam-to-(time slot, room) assignment problem, sharing one state
representation and cost function, so they can be compared fairly on
solution quality, convergence speed, and wall-clock time.

The project started (Review 1) as a pure algorithm-comparison exercise on
**synthetically generated** problem instances. It is now being extended
into a real tool: a user uploads a department's actual
courses/enrollments/rooms as CSVs through a frontend, and gets back a
generated timetable plus a report of any remaining conflicts. See §8 for
exactly what that extension needs and what's still undecided.

### Team (from the Review 1 proposal)

- **Shashwat Shekhar** — Hill-Climbing Lead. Built the shared state
  representation and cost function everyone else uses; built and tuned
  Hill-Climbing.
- **Suraj Doolipet** — Simulated Annealing Lead. Built and tuned SA —
  cooling schedule and acceptance probability.
- **Vignesh P C** — Genetic Algorithm & Experiment Lead. Built and tuned
  the GA — crossover, mutation, selection; set up the experiment harness.

### Collaboration

The repo has a second collaborator (a friend of the project owner) with
**Write** access on GitHub, who may also be working through Claude Code
sessions of their own. All remaining work is tracked as GitHub Issues
(#1-#16) rather than loose TODOs — see §10 for the full list and
dependency chain, and §11 for how to avoid two sessions/people stepping on
the same issue at once.

### ⚠️ Important: the proposal's own declaration

The submitted Review 1 proposal states: *"We didn't use any LLM tools to
write this proposal, and we're not planning to use any for the actual AI
core either."* The actual implementation (this codebase) was built with
Claude Code. Whoever owns this repo should be aware of that discrepancy
relative to what was declared, and should personally understand every
algorithm well enough to explain and defend it — treat this code as a
starting point you're responsible for, not a black box, and check your
course's policy on AI-assisted work before submitting.

---

## 2. The AI formulation (as specified in the proposal — do not drift from this without updating the proposal too)

This is a **local-search problem**, not classical search: there's no goal
path to find, just a state space with a cost function to minimize.

- **State**: one complete timetable — every exam assigned to some (time
  slot, room) pair. Represented in code as `Assignment = List[Tuple[int,
  int]]`, index = exam index, value = `(slot_idx, room_idx)`.
- **Initial state**: Hill-Climbing and SA start from a *fully random*
  timetable (every exam thrown into a random slot/room, no clash
  avoidance — violations are punished by the cost function, not blocked
  upfront). GA starts with a whole *population* of random timetables.
- **Actions/operators**: a *shift* (move one exam to a different
  slot/room) or a *swap* (trade the slot/room of two exams). HC looks at
  every possible shift and swap each round and takes the single best
  (steepest-descent). GA instead uses tournament selection + single-point
  crossover + mutation + elitism.
- **Objective/cost function**: a weighted sum of hard violations (weight
  10) and soft violations (weight 1). Cost 0 = a fully valid timetable.
- **Goal test**: `cost(state) == 0`. If the iteration/generation budget
  runs out first, return the best (lowest-cost) state found.
- **Termination**: HC stops when no move improves the state, or at
  `max_iters`. SA's temperature decays geometrically (`T *= alpha`) until
  it drops below `min_temp`, or `max_iters` is hit. GA stops at
  `max_generations`, or once the best fitness plateaus for
  `plateau_limit` generations.

### The cost function, precisely (`exam_timetable/cost.py`)

**Hard violations (weight 10 each):**
1. A room asked to hold more students than its capacity.
2. Two different exams assigned to the same (slot, room) — a room clash.
3. A student with two exams in the same time slot — double-booked.

**Soft violations (weight 1 each), computed per (student, day):**
4. *Bunching*: more than one exam for that student on the same day
   contributes `(distinct_periods_used - 1)`.
5. *Back-to-back*: any two of that student's exams in adjacent periods on
   the same day, `+1` per adjacent pair.

These weights (10 / 1) and all algorithm hyperparameters are **initial
defaults, not tuned** — the proposal explicitly defers tuning to Review 2.
Don't treat current numbers as final results; treat them as "the pipeline
works end-to-end and produces plausible output."

---

## 3. Current status (as of this writing)

| Phase | Status | Issue |
|---|---|---|
| Proposal / AI formulation (Review 1) | Done — see §2 | — |
| Core engine (state, cost, operators) | Done, tested | — |
| Three algorithms implemented | Done | — |
| Hill-Climbing performance (exhaustive search at scale) | Fixed — see §5 | — |
| SA cooling-schedule bug | Fixed — see §5 | — |
| GA mutation-operator bug | Fixed — see §5 | — |
| Clean experiment run with the above fixes applied | **Not yet done** — see §6 | #1 |
| Hyperparameter tuning | Not started | #16 |
| Results write-up / analysis for the report | Not started | #2 |
| CSV schema + sample files | Done — `docs/csv_schema.md`, `data/sample/` (PR #18) | #3 |
| CSV loader (real data instead of synthetic) | Done — `csv_loader.py` (PR #18) | #4 |
| Frontend stack decision | Done — Streamlit, see §8.3 | #5 |
| Frontend MVP | Done — `app.py` (PR #18) | #6 |
| Timetable grid display | Done (PR #18) | #7 |
| Violations report display | Done — `report.py` (PR #18) | #8 |
| "Compare all three" in frontend | Done (PR #18) | #9 |
| Export/download timetable | Done — CSV + violations .txt (PR #18) | #10 |
| Final report + presentation | Not started | #11 |
| AI-assistance disclosure decision | Not started | #12 |
| Non-uniform time slots | Not started (stretch) | #13 |
| Pre-locked exams | Not started (stretch) | #14 |
| Room-type restrictions | Not started (stretch) | #15 |
| Git repo / GitHub / Issues tracker | Done — pushed to `origin/main`, issues filed | — |

**If you're picking this up fresh: check GitHub Issues first for anything
already assigned or in-progress (§11), then take the highest-priority
unblocked issue. Issue #1 (rerun the experiment, confirm SA/GA now
compete with HC) has no dependencies and is the natural starting point if
nothing else is already claimed.**

---

## 4. Architecture

```
exam_timetable/
  models.py        Course, Room, TimeSlot, ProblemInstance (the data model)
  generator.py      synthetic problem-instance generator (seeded, reproducible)
  state.py          Assignment type + random_assignment/shifted/swapped helpers
  cost.py           evaluate() (full recompute) + incremental delta-cost functions
  operators.py      move generation, crossover, mutation, tournament selection
  result.py         SearchResult — common return type for all three algorithms
  algorithms/
    hill_climbing.py        exhaustive neighborhood, scored via delta-cost
    simulated_annealing.py  geometric cooling, Metropolis acceptance
    genetic_algorithm.py    memetic GA: tournament selection + crossover + per-gene mutation +
                            elitism + fast cost-guided local search per child (docs/ga_memetic.md)
  experiment.py     runs all three algorithms on 10/30/60-exam instances,
                    writes results/comparison.csv and results/plots/*.png
  cli.py            argparse entry point (`solve` and `experiment` subcommands)
  csv_loader.py     load_instance_from_csv(): courses/enrollments/rooms CSVs -> ProblemInstance
  report.py         violations report (which hard/soft violations remain) for the frontend
  palette.py        one fixed colour per algorithm, shared by plots and the frontend
app.py              Streamlit frontend (`streamlit run app.py`)
data/sample/        sample courses/enrollments/rooms CSVs (schedulable on the default 5x3 grid)
docs/csv_schema.md  the CSV input schema
scripts/make_sample_data.py   regenerates data/sample/enrollments.csv (seeded)
tests/
  test_cost.py          hand-crafted scenarios for each violation type
  test_cost_delta.py    property test: delta_shift/delta_swap must exactly
                        match evaluate(new) - evaluate(old), checked across
                        20 random instances x 30 random moves each, for both
                        move types — this is the test that would catch a
                        regression in the performance optimization in §5
  test_state.py          random_assignment / shifted / swapped correctness
  test_generator.py      generated instances are well-formed and reproducible
  test_algorithms.py     smoke tests: each algorithm runs, never regresses
                        (history is non-increasing), returns a valid assignment
  test_csv_loader.py     CSV loader: valid input and each rejected-input case
  test_ga_memetic.py     GA local search: fast best_shift == brute force delta_shift,
                        in-place state stays in sync, tracked cost == evaluate()
  test_sample_data.py    the shipped sample is schedulable on the default grid
main.py             `python main.py <solve|experiment> ...`
```

### Data flow

```
ProblemInstance (courses, rooms, slots, num_students)
        |
        v
  random_assignment()  -->  Assignment (the state)
        |
        v
  algorithm.run(instance, ...)  -->  SearchResult(assignment, cost, history, ...)
```

`ProblemInstance` is the seam: today it's built by `generator.py`
(synthetic), but the algorithms, cost function, and state code have zero
knowledge of where it came from. This is exactly the seam §8's CSV
ingestion plugs into — building a `ProblemInstance` from real data
requires **no changes to `cost.py`, `operators.py`, `state.py`, or any
algorithm**.

---

## 5. Design decisions and bugs already found/fixed (read before re-deriving these)

### 5.1 Why there's both `evaluate()` and delta-cost functions in `cost.py`

Hill-Climbing's exhaustive neighborhood means every round evaluates
~`num_exams * num_slots * num_rooms` shift candidates plus
~`num_exams choose 2` swap candidates — around 9,000 candidates/round at
60 exams. Scoring each with a full `evaluate()` call (which rescans every
student enrollment, ~1,300 of them at 60 exams) made a single 60-exam HC
run not finish within several minutes.

Fix: `build_snapshot(instance, assignment)` precomputes the aggregates
`evaluate()` would otherwise rebuild, **once per round**. Each candidate
move's cost delta is then computed by `delta_shift()` / `delta_swap()`,
touching only the students actually enrolled in the exam(s) that move —
not the whole instance. This took a 60-exam HC run from "didn't finish in
180s+" to ~70-90s.

**This is the kind of code that's easy to get subtly wrong** (e.g. double
decrementing the student_slot_count), which is why
`tests/test_cost_delta.py` exists specifically to brute-force-verify
`delta_shift`/`delta_swap` against `evaluate()` on many random
instances/moves. If you touch `cost.py`'s delta functions, re-run that
test — don't trust manual reasoning alone.

Note the swap-delta math has a non-obvious correctness point: a student
enrolled in *both* exams being swapped sees zero net change to their
schedule (they still have one exam at each of the two slots, just from
the other course), so only students enrolled in exactly one of the two
courses contribute to the delta. See the comment in `delta_swap()`.

### 5.2 SA's cooling schedule was silently handing back its iteration budget

Original code: `alpha: float = 0.995` fixed, `min_temp: float = 1e-3`,
loop breaks when `temp < min_temp`. With `initial_temp=50`, temperature
crosses `min_temp` after `log(1e-3/50)/log(0.995) ≈ 2159` iterations —
**regardless of `max_iters`**. Every experiment run showed
`iters=2159` for SA no matter what `max_iters` was set to, meaning SA was
silently using under half its nominal 5000-iteration budget, and the back
half of even those 2159 iterations ran at a temperature too low for
`exp(-delta/T)` to meaningfully accept worse moves — i.e. it degraded
into a weak single-random-move hill climb for a good chunk of its run.

Fix (`simulated_annealing.py`): when `alpha` isn't explicitly passed, it's
now derived as `alpha = (min_temp / initial_temp) ** (1 / max_iters)`, so
the cooling schedule spans exactly `max_iters` steps by construction.

### 5.3 GA's mutation was nearly inert

Original code: `mutate_single()` reassigned exactly *one* exam, and only
fired with probability `mutation_rate=0.3` — so 70% of children were pure
crossover with zero mutation. Worse, single-point crossover over an
arbitrary exam-index ordering doesn't preserve any meaningful structure
(course index 5 and course index 6 have no inherent relationship), so
crossover was mostly scrambling rather than combining good partial
solutions. Net effect: GA barely explored past its initial random
population.

Fix (`operators.py`'s `mutate()`, used by `genetic_algorithm.py`): every
exam is now independently mutated with a small per-gene probability
(`gene_mutation_rate`, default 0.05) **every generation, for every
child** — no outer all-or-nothing gate. At least one gene is guaranteed
to mutate if none did by chance, so mutation always does something.

### 5.4 Observed effect of 5.2 + 5.3 (not yet confirmed — see §6)

Before these fixes, Hill-Climbing beat SA and GA on every problem size,
which runs counter to the proposal's own hypothesis (HC should be fast
but prone to getting stuck; SA/GA should eventually do better by escaping
local optima). The working theory is that this was an artifact of SA/GA
being starved of effective search budget, not a real algorithmic result —
HC's advantage came from evaluating ~9,000 moves/round and always taking
the best, which is a much larger effective budget than SA's single random
proposal per iteration or GA's near-inert mutation. **This has not yet
been re-confirmed with a clean experiment run** — the first rerun attempt
was interrupted by the host machine running low on memory (unrelated to
the code; the harness killed the background process as a safety measure).
Re-running `python main.py experiment` is the next concrete step.

### 5.5 Windows/git gotcha already hit once

Pasting a `git commit -m "..."` command from a source that uses smart/curly
quotes (`"..."` instead of straight `"..."`) into `cmd.exe` silently
breaks quoting — `cmd.exe` doesn't treat curly quotes as delimiters, so
the message gets split into dozens of words, each misinterpreted as a
pathspec. It may still produce a commit, just with a mangled message (this
happened once in this repo's history and was fixed with `git commit
--amend` + `git push --force-with-lease`). When committing from an agent
session, prefer a heredoc (`git commit -m "$(cat <<'EOF' ... EOF)"`) over
an inline `-m "..."` string to sidestep this entirely.

---

## 6. Immediate next step: re-validate the experiment (Issue #1)

This is tracked as GitHub Issue #1 — claim it there (see §11) before
starting, so it's not duplicated. Run:
```
python main.py experiment
```
This regenerates `results/comparison.csv` and `results/plots/*.png` for
10/30/60-exam synthetic instances across all three algorithms, using the
fixes from §5.2 and §5.3. Confirm:
- SA now actually uses close to its full `max_iters` budget (check
  `iterations` in the CSV — should be much closer to 5000 than the old
  ~2159, unless it hits cost 0 first).
- Whether SA and/or GA now match or beat HC's final cost at any problem
  size, especially 60 exams — this is the comparison the proposal's
  Review 2 narrative depends on.

Expect this to take a few minutes wall-clock, dominated by HC's
exhaustive search at 60 exams (~70-90s observed). If a background run
gets killed for low system memory, that's the harness's safety behavior,
not a code bug — retry once memory frees up, don't "fix" the algorithm in
response to that.

---

## 7. Running things

```bash
pip install -r requirements.txt     # matplotlib, pytest, streamlit
pytest                               # 17 tests, should all pass in ~1-2s
                                      # (test_algorithms.py's SA case takes
                                      # longer than it used to post-§5.2 —
                                      # that's expected, not a regression)

python main.py solve --algorithm hc --exams 10
python main.py solve --algorithm sa --exams 30
python main.py solve --algorithm ga --exams 60

python main.py experiment            # full comparison, writes results/

streamlit run app.py                 # the frontend (upload CSVs or use demo data)
```

`py` is the working Python launcher on this Windows machine (plain
`python`/`python3` are not on PATH); use `py -m pytest`, `py main.py ...`
if invoking directly rather than through an already-configured shell
alias.

---

## 8. The pivot: real data + frontend (built — PR #18)

The direction, confirmed with the project owner: stop being
synthetic-data-only and become a tool that takes a real department's data
and produces a real timetable.

### 8.1 Required inputs (maps 1:1 onto the existing data model)

| File | Columns | Maps to | Why required |
|---|---|---|---|
| `courses.csv` | `course_id`, `course_name` | `Course` | Defines the exams to schedule |
| `enrollments.csv` | `student_id`, `course_id` (one row per pair) | derives each `Course.students` | **The** source of every student-side conflict check (double-booking, back-to-back, bunching). Without this, no student-level cost signal exists at all. |
| `rooms.csv` | `room_id`, `capacity` | `Room` | Capacity-violation and room-clash checks |
| exam period structure | likely a simple config (days × periods/day), not a file, unless slots are non-uniform (then a `slots.csv` with `slot_id, day, period` or similar) | `TimeSlot` | Defines the grid of (day, period) slots |

Optional, display-only (don't affect the algorithm): student display
names, course display names/codes.

Explicitly **not supported by the current model** — would need changes to
`models.py` and `cost.py` to add: exams with different durations
(currently every exam = exactly one slot), pre-locked exams (some exam
already fixed before the solver runs), room-type restrictions (e.g. a
course needing a lab specifically, not just any sufficiently large room),
invigilator/staff conflicts.

### 8.2 What the frontend needs to do

1. **Input**: upload the CSVs above (or fill the slot-structure config).
2. **Processing**: let the user pick one algorithm, or "run all three and
   compare." Show progress — HC can take real time at larger sizes.
3. **Output**: the actual timetable as a readable grid (exam → day/period/
   room), a violations report (which hard violations remain, if any;
   which students have back-to-backs), and — if "compare all three" was
   picked — the same cost/iterations/time comparison the experiment
   harness already produces, just computed on the real uploaded instance
   instead of a synthetic one.

### 8.3 Decision: frontend stack — Streamlit

Decided: **Streamlit** (`app.py`, merged in PR #18). The two options that
were discussed:

- **Streamlit** (recommended default if no strong reason otherwise): a
  single Python process, built-in file upload + dataframe/table + chart
  widgets, no separate API/backend to design or deploy. Much less work,
  and the algorithms are the actual graded substance here, not the UI
  polish.
- **Full web app** (React frontend + FastAPI backend): more "product"-
  like, but real extra work — API design, CORS, two services to run/
  deploy instead of one. Only worth it if there's a specific reason (e.g.
  wanting this as a portfolio piece beyond the course).

The full web app option was not pursued.

### 8.4 Implementation: `csv_loader.py`

Implemented as `exam_timetable/csv_loader.py`, exposing
`load_instance_from_csv(courses_source, enrollments_source, rooms_source,
days, periods_per_day)`, which returns `(ProblemInstance, labels)`. It is built the same way
`generator.py`'s `generate_instance()` is, just reading real rows instead
of sampling them. This is additive — `generator.py` stays for synthetic
testing/experiments; the CSV loader is a second, parallel way to build a
`ProblemInstance`. Nothing downstream (state, cost, operators,
algorithms, experiment harness) needs to know or care which one was used.

---

## 9. Things NOT to do without checking first

- Don't change the hard/soft weight constants (`HARD_WEIGHT = 10`,
  `SOFT_WEIGHT = 1` in `cost.py`) without updating the proposal/report —
  the proposal explicitly frames these as "tuned in Review 2," so a
  change should be a deliberate, documented tuning decision, not an
  incidental edit.
- Don't add external optimization/metaheuristic libraries (DEAP, PyGAD,
  scipy.optimize, etc.) — the proposal explicitly declares the state,
  operators, and cost function are hand-implemented, not library-based.
  matplotlib (plotting only) is the one external dependency beyond
  pytest.
- Don't force-push or amend commits that are already on `origin/main`
  without explicit confirmation from the project owner — git history on
  the shared repo should be treated as public once pushed.
- Don't edit `cost.py`'s delta functions without running
  `tests/test_cost_delta.py` immediately after — see §5.1.
- Don't start work on an issue without checking GitHub first for an
  existing branch/PR/assignee on it — see §11. With two people (and
  possibly multiple Claude sessions) on this repo, duplicated work is the
  most likely failure mode now, not a code bug.
- Don't merge straight to `main` without a PR if branch protection has
  been turned on (check — this was discussed but may or may not be set up
  yet). If unsure, open a PR anyway; it costs little and avoids surprises.

---

## 10. Issue tracker (full list + dependency chain)

Standing copy of all 16 tracked issues, in case GitHub itself isn't handy
mid-session. The numbers below match GitHub (an earlier version of this
table was off by one from #2 onwards); if they ever drift again, GitHub is
the source of truth and this table is the dependency *shape*.

| # | Title | Depends on | Labels | Status |
|---|---|---|---|---|
| 1 | Rerun full experiment with SA/GA fixes and validate results | none | experiment, priority-high | open |
| 2 | Write results analysis for the Review 2 report | #16 | documentation, report, priority-high | open |
| 3 | Design and document the CSV input schema | none | csv-ingestion, documentation, priority-high | done (PR #18) |
| 4 | Build the CSV loader (`csv_loader.py`) | #3 | csv-ingestion, priority-high | done (PR #18) |
| 5 | Decide the frontend stack | none (blocking decision) | frontend, decision, priority-high | done (Streamlit) |
| 6 | Build frontend MVP: upload CSVs -> run a solve | #4, #5 | frontend, priority-high | done (PR #18) |
| 7 | Timetable grid display | #6 | frontend, priority-medium | done (PR #18) |
| 8 | Violations report display | #6 | frontend, priority-medium | done (PR #18) |
| 9 | Compare all three algorithms mode in the frontend | #6 | frontend, experiment, priority-medium | done (PR #18) |
| 10 | Export/download the generated timetable | #7 | frontend, priority-low | done (PR #18) |
| 11 | Final report and presentation materials | #2, #9 | documentation, report, priority-high | open |
| 12 | Resolve the AI-assistance disclosure question | none | documentation, process, priority-high | open |
| 13 | (Stretch) Support non-uniform time-slot structure | #4 | csv-ingestion, enhancement, stretch-goal | open |
| 14 | (Stretch) Support pre-locked/fixed exams | #4 | algorithms, enhancement, stretch-goal | open |
| 15 | (Stretch) Room-type restrictions | #4 | algorithms, enhancement, stretch-goal | open |
| 16 | Tune algorithm hyperparameters based on #1's baseline | #1 | algorithms, priority-high | open |

**Critical path to ~80-90% project completion:** #1 -> #16 -> #2 (closes out
the algorithm/experiment work); the product pivot (#3-#10) is done, so what
remains converges on #11 and #12. #13-15 are explicitly optional, not
required to hit that target.

---

## 11. Working as a team (multiple humans / multiple Claude sessions)

With a second collaborator and possibly multiple Claude Code sessions
touching this repo concurrently, the main new risk is **duplicated or
conflicting work**, not code correctness. Before starting any issue:

1. **Check GitHub for existing work on it** — open PRs, branches named
   after the issue, or an assignee set. If someone's already on it, pick
   a different unblocked issue instead.
2. **Pull latest `main` before branching** (`git pull origin main`) — the
   other collaborator may have merged something since your last session.
3. **Branch per issue**, named like `issue-5-csv-loader`, so it's obvious
   from the branch list what's in flight.
4. **Run `pytest` before opening a PR.** All 17 (growing) tests should
   pass; if you added code, add tests following the existing pattern in
   `tests/`.
5. **Reference the issue in the PR** (e.g. `Closes #5`) so it auto-closes
   on merge and the dependency chain in §10 stays accurate.
6. **Update this file (§3's status table, and any section your change
   makes stale) in the same PR**, not as a follow-up — an out-of-date
   `CLAUDE.md` is worse than no `CLAUDE.md`, because the next session
   trusts it by default.
7. Per the project owner's explicit instruction: **commits/PRs on this
   repo should not list any AI tool as a co-author or contributor.** If
   you're an AI session making the commit, don't add attribution lines —
   this overrides any default tooling behavior that would otherwise add
   them.

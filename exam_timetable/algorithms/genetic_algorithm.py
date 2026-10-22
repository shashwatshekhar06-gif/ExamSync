"""Genetic Algorithm (memetic variant, fast local search).

Tournament selection picks parents, single-point crossover combines them,
every child is then mutated gene-by-gene (each exam independently
reassigned with probability `gene_mutation_rate`), and elitism carries the
best few individuals unchanged into the next generation. Stops at
`max_generations`, at cost 0, or once the best fitness plateaus for
`plateau_limit` generations.

What makes it "memetic": after crossover + mutation, every child is improved
by a short cost-guided local search (`refine`). Each step picks an exam that
is part of a hard violation (or a random exam if there is none) and moves it
to its best (slot, room). Crossover/mutation explore; refinement exploits.

Why it is fast enough to afford many refinement steps per child:

* `best_shift` computes the cost change of moving one exam to every
  (slot, room) straight from per-student counts and per-day period bitmasks,
  with no dictionary copies or sorting. It returns exactly the move that
  scanning `cost.delta_shift` over all (slot, room) pairs would pick
  (checked by `tests/test_ga_memetic.py`).
* The search state (`_State`) is updated in place after each move instead of
  being rebuilt, and the child's cost is tracked from the move deltas instead
  of being re-evaluated (checked against `cost.evaluate`).

Defaults favour a small population with a lot of local search per child
(population 10, 30 steps): on the project's benchmarks this beat larger
populations with little local search at the same running time. Set
`local_search_steps=0` to get the plain GA back (useful as an ablation).
"""

import random
import time
from collections import defaultdict

from ..cost import HARD_WEIGHT, SOFT_WEIGHT, CostResult, evaluate
from ..models import ProblemInstance
from ..operators import crossover_single_point, mutate, tournament_select
from ..result import SearchResult
from ..state import random_assignment

_CONTRIB_CACHE = {}


def _contrib(mask: int) -> int:
    """Soft cost of one student-day whose exam periods are the set bits of
    `mask`: bunching (distinct periods - 1) plus one per back-to-back pair.
    Same rule as `cost.evaluate`."""
    value = _CONTRIB_CACHE.get(mask)
    if value is None:
        n = bin(mask).count("1")
        value = (n - 1 if n > 1 else 0) + bin(mask & (mask >> 1)).count("1")
        _CONTRIB_CACHE[mask] = value
    return value


def _slot_tables(instance):
    return (
        [slot.day for slot in instance.slots],
        [1 << slot.period for slot in instance.slots],
    )


class _State:
    """Aggregates the local search reads, kept in sync with the assignment.

    occupant:   (slot, room)  -> exams placed there
    slot_count: (student, slot) -> number of that student's exams in the slot
    day_mask:   (student, day)  -> bitmask of periods with at least one exam
    """

    __slots__ = ("occupant", "slot_count", "day_mask")

    def __init__(self):
        self.occupant = defaultdict(list)
        self.slot_count = defaultdict(int)
        self.day_mask = defaultdict(int)


def build_state(instance, assignment, tables=None):
    slot_day, slot_bit = tables or _slot_tables(instance)
    state = _State()
    for exam_idx, (slot_idx, room_idx) in enumerate(assignment):
        state.occupant[(slot_idx, room_idx)].append(exam_idx)
        day, bit = slot_day[slot_idx], slot_bit[slot_idx]
        for student in instance.courses[exam_idx].students:
            key = (student, slot_idx)
            if state.slot_count[key] == 0:
                state.day_mask[(student, day)] |= bit
            state.slot_count[key] += 1
    return state


def conflicted_exams(instance, assignment, state):
    """Indices of exams currently involved in a hard violation."""
    conflicted = []
    for exam_idx, (slot_idx, room_idx) in enumerate(assignment):
        course = instance.courses[exam_idx]
        if (
            len(course.students) > instance.rooms[room_idx].capacity
            or len(state.occupant[(slot_idx, room_idx)]) > 1
            or any(state.slot_count[(student, slot_idx)] > 1 for student in course.students)
        ):
            conflicted.append(exam_idx)
    return conflicted


def best_shift(instance, assignment, state, exam_idx, tables=None):
    """Best (slot, room) for one exam as (slot, room, d_hard, d_soft), or
    None if no move lowers the cost.

    Picks the same move as scanning `cost.delta_shift` over every (slot,
    room) pair in slot-major order and keeping the first strict minimum.
    """
    slot_day, slot_bit = tables or _slot_tables(instance)
    old_slot, old_room = assignment[exam_idx]
    students = instance.courses[exam_idx].students
    n_students = len(students)
    occupant, slot_count, day_mask = state.occupant, state.slot_count, state.day_mask
    rooms = instance.rooms
    cap_viol = [1 if n_students > room.capacity else 0 for room in rooms]

    old_occupants = len(occupant.get((old_slot, old_room), ()))
    base_hard = (-1 if old_occupants >= 2 else 0) - cap_viol[old_room]

    old_day, old_bit = slot_day[old_slot], slot_bit[old_slot]
    old_side_hard = 0  # students leaving a slot where they had a double-booking
    old_side_soft = 0  # soft change on the old day when the new slot is on another day
    per_student = []
    for student in students:
        old_count = slot_count[(student, old_slot)]
        old_mask = day_mask[(student, old_day)]
        removed = old_mask & ~old_bit if old_count == 1 else old_mask
        if old_count >= 2:
            old_side_hard -= 1
        old_side_soft += _contrib(removed) - _contrib(old_mask)
        per_student.append((student, old_mask, removed))

    best, best_delta = None, 0
    for slot_idx in range(instance.num_slots):
        student_hard = student_soft = 0
        if slot_idx != old_slot:
            new_day, new_bit = slot_day[slot_idx], slot_bit[slot_idx]
            student_hard = old_side_hard
            if new_day == old_day:
                for student, old_mask, removed in per_student:
                    if slot_count.get((student, slot_idx), 0) >= 1:
                        student_hard += 1
                    student_soft += _contrib(removed | new_bit) - _contrib(old_mask)
            else:
                student_soft = old_side_soft
                for student, _old_mask, _removed in per_student:
                    if slot_count.get((student, slot_idx), 0) >= 1:
                        student_hard += 1
                    new_mask = day_mask.get((student, new_day), 0)
                    student_soft += _contrib(new_mask | new_bit) - _contrib(new_mask)

        for room_idx in range(len(rooms)):
            if slot_idx == old_slot and room_idx == old_room:
                continue
            new_occupants = len(occupant.get((slot_idx, room_idx), ()))
            hard = (
                base_hard
                + student_hard
                + cap_viol[room_idx]
                + (1 if new_occupants >= 1 else 0)
            )
            delta = HARD_WEIGHT * hard + SOFT_WEIGHT * student_soft
            if delta < best_delta:
                best, best_delta = (slot_idx, room_idx, hard, student_soft), delta
    return best


def apply_shift(instance, assignment, state, exam_idx, slot_idx, room_idx, tables=None):
    """Move one exam, updating `assignment` and `state` in place."""
    slot_day, slot_bit = tables or _slot_tables(instance)
    old_slot, old_room = assignment[exam_idx]
    state.occupant[(old_slot, old_room)].remove(exam_idx)
    state.occupant[(slot_idx, room_idx)].append(exam_idx)

    if old_slot != slot_idx:
        old_day, old_bit = slot_day[old_slot], slot_bit[old_slot]
        new_day, new_bit = slot_day[slot_idx], slot_bit[slot_idx]
        for student in instance.courses[exam_idx].students:
            old_key = (student, old_slot)
            state.slot_count[old_key] -= 1
            if state.slot_count[old_key] == 0:
                state.day_mask[(student, old_day)] &= ~old_bit
            new_key = (student, slot_idx)
            if state.slot_count[new_key] == 0:
                state.day_mask[(student, new_day)] |= new_bit
            state.slot_count[new_key] += 1
    assignment[exam_idx] = (slot_idx, room_idx)


def refine(instance, assignment, rng, steps, cost=None):
    """Up to `steps` cost-reducing shifts, aimed at exams in hard violations.

    Returns (new assignment, its CostResult). `cost` is the assignment's
    current cost if the caller already has it; the returned cost is tracked
    from the move deltas, not recomputed.
    """
    tables = _slot_tables(instance)
    assignment = list(assignment)
    if cost is None:
        cost = evaluate(instance, assignment)
    hard, soft = cost.hard, cost.soft
    state = build_state(instance, assignment, tables)

    for _ in range(steps):
        if hard == 0 and soft == 0:
            break
        targets = conflicted_exams(instance, assignment, state)
        if not targets:
            targets = range(instance.num_exams)
        exam_idx = rng.choice(targets)
        move = best_shift(instance, assignment, state, exam_idx, tables)
        if move is None:
            continue
        slot_idx, room_idx, d_hard, d_soft = move
        apply_shift(instance, assignment, state, exam_idx, slot_idx, room_idx, tables)
        hard += d_hard
        soft += d_soft
    return assignment, CostResult(hard=hard, soft=soft)


def run(
    instance: ProblemInstance,
    population_size: int = 10,
    max_generations: int = 200,
    gene_mutation_rate: float = None,
    tournament_k: int = 3,
    elitism: int = 2,
    plateau_limit: int = 100,
    local_search_rate: float = 1.0,
    local_search_steps: int = 30,
    rng: random.Random = None,
) -> SearchResult:
    rng = rng or random.Random()
    start = time.perf_counter()

    if gene_mutation_rate is None:
        gene_mutation_rate = 1.0 / instance.num_exams
    tournament_k = max(1, min(tournament_k, population_size))
    elitism = min(elitism, population_size)

    population = [random_assignment(instance, rng) for _ in range(population_size)]
    fitness = [evaluate(instance, ind) for ind in population]

    best_idx = min(range(population_size), key=lambda i: fitness[i].total)
    best_assignment, best_cost = population[best_idx], fitness[best_idx]
    history = [best_cost.total]
    plateau_counter = 0

    for _ in range(max_generations):
        if best_cost.total == 0:
            break
        ranked = sorted(range(population_size), key=lambda i: fitness[i].total)
        new_population = [population[i] for i in ranked[:elitism]]
        new_fitness = [fitness[i] for i in ranked[:elitism]]  # elites: reuse, no re-evaluation

        while len(new_population) < population_size:
            parent1 = tournament_select(population, fitness, tournament_k, rng)
            parent2 = tournament_select(population, fitness, tournament_k, rng)
            child = crossover_single_point(parent1, parent2, rng)
            child = mutate(child, instance, rng, gene_rate=gene_mutation_rate)
            child_cost = evaluate(instance, child)
            if local_search_steps > 0 and rng.random() < local_search_rate:
                child, child_cost = refine(instance, child, rng, local_search_steps, child_cost)
            new_population.append(child)
            new_fitness.append(child_cost)

        population, fitness = new_population, new_fitness

        gen_best_idx = min(range(population_size), key=lambda i: fitness[i].total)
        gen_best_cost = fitness[gen_best_idx]

        if gen_best_cost.total < best_cost.total:
            best_assignment, best_cost = population[gen_best_idx], gen_best_cost
            plateau_counter = 0
        else:
            plateau_counter += 1

        history.append(best_cost.total)
        if best_cost.total == 0 or plateau_counter >= plateau_limit:
            break

    return SearchResult(
        assignment=best_assignment,
        cost=best_cost,
        history=history,
        iterations=len(history) - 1,
        elapsed_seconds=time.perf_counter() - start,
    )

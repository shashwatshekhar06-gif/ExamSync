"""Tests for the GA's fast local-refinement (memetic) step."""

import random

import pytest

from exam_timetable.algorithms import genetic_algorithm
from exam_timetable.algorithms.genetic_algorithm import (
    apply_shift,
    best_shift,
    build_state,
    refine,
)
from exam_timetable.cost import build_snapshot, delta_shift, evaluate
from exam_timetable.generator import generate_instance
from exam_timetable.state import random_assignment


def _instance_and_assignment(seed):
    rng = random.Random(seed)
    instance = generate_instance(rng.choice([6, 10, 30]), seed=seed)
    return instance, random_assignment(instance, rng), rng


@pytest.mark.parametrize("seed", range(20))
def test_best_shift_matches_brute_force(seed):
    """The fast search must pick the same move, with the same cost change, as
    trying every (slot, room) with delta_shift."""
    instance, assignment, _ = _instance_and_assignment(seed)
    snapshot = build_snapshot(instance, assignment)
    state = build_state(instance, assignment)

    for exam_idx in range(min(instance.num_exams, 6)):
        best_move, best_delta = None, 0
        for slot_idx in range(instance.num_slots):
            for room_idx in range(instance.num_rooms):
                d = delta_shift(instance, assignment, snapshot, exam_idx, slot_idx, room_idx)
                if d < best_delta:
                    best_move, best_delta = (slot_idx, room_idx), d
        fast = best_shift(instance, assignment, state, exam_idx)
        assert (fast[:2] if fast else None) == best_move


@pytest.mark.parametrize("seed", range(10))
def test_apply_shift_keeps_state_in_sync(seed):
    """After random moves, the incrementally updated state must equal one
    rebuilt from scratch."""
    instance, assignment, rng = _instance_and_assignment(seed)
    state = build_state(instance, assignment)
    for _ in range(25):
        exam_idx = rng.randrange(instance.num_exams)
        apply_shift(
            instance, assignment, state, exam_idx,
            rng.randrange(instance.num_slots), rng.randrange(instance.num_rooms),
        )
    fresh = build_state(instance, assignment)
    assert {k: sorted(v) for k, v in state.occupant.items() if v} == {
        k: sorted(v) for k, v in fresh.occupant.items() if v
    }
    assert {k: v for k, v in state.slot_count.items() if v} == dict(fresh.slot_count)
    assert {k: v for k, v in state.day_mask.items() if v} == dict(fresh.day_mask)


@pytest.mark.parametrize("seed", range(10))
def test_refine_cost_tracking_matches_evaluate(seed):
    instance, assignment, rng = _instance_and_assignment(seed)
    refined, tracked = refine(instance, assignment, rng, steps=10)
    assert tracked == evaluate(instance, refined)


@pytest.mark.parametrize("seed", range(10))
def test_refine_never_increases_cost(seed):
    instance, assignment, rng = _instance_and_assignment(seed)
    before = evaluate(instance, assignment).total
    _, after = refine(instance, assignment, rng, steps=5)
    assert after.total <= before


def test_refine_does_not_mutate_its_input():
    instance, assignment, rng = _instance_and_assignment(0)
    original = list(assignment)
    refine(instance, assignment, rng, steps=5)
    assert assignment == original


def test_run_reported_cost_matches_evaluate():
    instance = generate_instance(num_exams=10, seed=1)
    result = genetic_algorithm.run(
        instance, population_size=6, max_generations=8, local_search_steps=5,
        rng=random.Random(1),
    )
    assert result.cost == evaluate(instance, result.assignment)
    assert result.history[-1] == result.cost.total
    assert all(b <= a for a, b in zip(result.history, result.history[1:]))


def test_plain_ga_still_works_with_local_search_off():
    instance = generate_instance(num_exams=6, seed=0)
    result = genetic_algorithm.run(
        instance, population_size=10, max_generations=20, local_search_steps=0,
        rng=random.Random(0),
    )
    assert result.history[-1] <= result.history[0]
    assert result.cost.total == result.history[-1]

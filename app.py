"""Streamlit frontend for the Automated Exam Timetable Generator.

Upload a department's courses/enrollments/rooms as CSVs (or use synthetic
demo data), run one algorithm or compare all three, and get back a
timetable grid, a violations report, and (in compare mode) the same
cost/iterations/time comparison the experiment harness produces - see
CLAUDE.md §8 for the full design, and docs/csv_schema.md for the CSV
format.

Run with:
    streamlit run app.py
"""

import random
from collections import defaultdict
from io import StringIO

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import streamlit as st

from exam_timetable.algorithms import genetic_algorithm, hill_climbing, simulated_annealing
from exam_timetable.csv_loader import CsvSchemaError, load_instance_from_csv
from exam_timetable.generator import generate_instance
from exam_timetable.palette import ALGORITHM_COLORS
from exam_timetable.report import build_violation_report

def default_period_labels(periods_per_day):
    """A sensible default label set for common period counts - e.g. 3
    periods/day reads much better as "Morning (9-12)" than "Period 1".
    Returns None (fall back to generic "Period N") for counts with no
    obvious default."""
    if periods_per_day == 3:
        return ["Morning (9-12)", "Noon (12-3)", "Evening (3-6)"]
    return None


def period_label(period_idx, period_labels):
    if period_labels and period_idx < len(period_labels):
        return period_labels[period_idx]
    return f"Period {period_idx + 1}"


ALGORITHMS = {
    "Hill-Climbing": lambda instance, rng, p: hill_climbing.run(
        instance, max_iters=p["hc_max_iters"], rng=rng
    ),
    "Simulated Annealing": lambda instance, rng, p: simulated_annealing.run(
        instance, max_iters=p["sa_max_iters"], rng=rng
    ),
    "Genetic Algorithm": lambda instance, rng, p: genetic_algorithm.run(
        instance, population_size=p["ga_population"], max_generations=p["ga_generations"], rng=rng
    ),
}


def build_exam_list(instance, assignment, room_labels, period_labels=None):
    """One row per exam — the easy-to-read view. The grid (below) shows
    room utilization across the whole week, but for a handful of exams
    it's mostly empty cells, which reads as confusing rather than
    informative; this list is what most people actually want to check."""
    room_names = room_labels or [f"Room {i}" for i in range(instance.num_rooms)]
    rows = []
    for exam_idx, (slot_idx, room_idx) in enumerate(assignment):
        slot = instance.slots[slot_idx]
        rows.append(
            (
                slot.day,
                slot.period,
                room_names[room_idx],
                {
                    "Course": instance.courses[exam_idx].name,
                    "Day": slot.day + 1,
                    "Time": period_label(slot.period, period_labels),
                    "Room": room_names[room_idx],
                    "Students": len(instance.courses[exam_idx].students),
                },
            )
        )
    rows.sort(key=lambda t: (t[0], t[1], t[2]))
    return [row for _, _, _, row in rows]


def build_grid(instance, assignment, room_labels, period_labels=None):
    room_names = room_labels or [f"Room {i}" for i in range(instance.num_rooms)]
    occupants = defaultdict(list)
    for exam_idx, (slot_idx, room_idx) in enumerate(assignment):
        occupants[(slot_idx, room_idx)].append(instance.courses[exam_idx].name)

    rows = []
    for slot_idx, slot in enumerate(instance.slots):
        row = {"Day": slot.day + 1, "Time": period_label(slot.period, period_labels)}
        for room_idx, room_name in enumerate(room_names):
            row[room_name] = ", ".join(occupants.get((slot_idx, room_idx), []))
        rows.append(row)
    return rows, room_names


def list_to_csv(exam_rows):
    buf = StringIO()
    fieldnames = ["Course", "Day", "Time", "Room", "Students"]
    buf.write(",".join(fieldnames) + "\n")
    for row in exam_rows:
        buf.write(",".join(str(row[f]).replace(",", ";") for f in fieldnames) + "\n")
    return buf.getvalue()


def render_comparison_charts(results):
    names = list(results.keys())
    colors = [ALGORITHM_COLORS.get(n, "#898781") for n in names]
    metrics = [
        ("final_cost", "Final cost (lower is better)", [results[n].cost.total for n in names]),
        ("iterations", "Iterations / generations used", [results[n].iterations for n in names]),
        ("elapsed_seconds", "Wall-clock time (s)", [results[n].elapsed_seconds for n in names]),
    ]
    cols = st.columns(3)
    for col, (_, title, values) in zip(cols, metrics):
        fig, ax = plt.subplots(figsize=(4, 3))
        ax.bar(names, values, color=colors)
        ax.set_title(title, fontsize=10)
        ax.tick_params(axis="x", labelrotation=20, labelsize=8)
        for spine in ("top", "right"):
            ax.spines[spine].set_visible(False)
        fig.tight_layout()
        col.pyplot(fig)
        plt.close(fig)


def main():
    st.set_page_config(page_title="Exam Timetable Generator", layout="wide")
    st.title("Automated Exam Timetable Generator")
    st.caption(
        "Local-search exam scheduling — Hill-Climbing, Simulated Annealing, and a "
        "Genetic Algorithm on the same exam-to-(slot, room) assignment problem."
    )

    instance = None
    labels = None

    with st.sidebar:
        st.header("1. Data")
        data_mode = st.radio("Data source", ["Upload CSVs", "Synthetic demo data"])

        st.subheader("Exam period structure")
        col1, col2 = st.columns(2)
        days = col1.number_input("Days", min_value=1, value=5, step=1)
        periods_per_day = col2.number_input("Periods/day", min_value=1, value=3, step=1)

        default_labels = default_period_labels(int(periods_per_day))
        label_text = st.text_input(
            "Period labels (comma-separated, optional)",
            value=", ".join(default_labels) if default_labels else "",
            help='E.g. "Morning (9-12), Noon (12-3), Evening (3-6)". Leave '
            'blank for generic "Period 1/2/3".',
        )
        period_labels = [s.strip() for s in label_text.split(",") if s.strip()] or None
        if period_labels and len(period_labels) != int(periods_per_day):
            st.caption(
                f"⚠️ Expected {int(periods_per_day)} period label(s), got "
                f"{len(period_labels)} — showing generic \"Period N\" instead."
            )
            period_labels = None

        if data_mode == "Upload CSVs":
            courses_file = st.file_uploader("courses.csv", type="csv")
            enrollments_file = st.file_uploader("enrollments.csv", type="csv")
            rooms_file = st.file_uploader("rooms.csv", type="csv")

            if courses_file and enrollments_file and rooms_file:
                try:
                    instance, labels = load_instance_from_csv(
                        courses_file.getvalue(),
                        enrollments_file.getvalue(),
                        rooms_file.getvalue(),
                        days=int(days),
                        periods_per_day=int(periods_per_day),
                    )
                except CsvSchemaError as e:
                    st.error(f"CSV problem: {e}")
            else:
                st.caption("See docs/csv_schema.md for the required columns, or try the sample files in data/sample/.")
        else:
            num_exams = st.slider("Number of exams", 5, 200, 30)
            col3, col4 = st.columns(2)
            num_students = col3.number_input("Students", min_value=10, value=300, step=10)
            num_rooms = col4.number_input("Rooms", min_value=1, value=6, step=1)
            demo_seed = st.number_input("Generator seed", min_value=0, value=42, step=1)
            instance = generate_instance(
                int(num_exams),
                num_students=int(num_students),
                num_rooms=int(num_rooms),
                days=int(days),
                periods_per_day=int(periods_per_day),
                seed=int(demo_seed),
            )

        st.header("2. Algorithm")
        mode = st.radio("Mode", list(ALGORITHMS.keys()) + ["Compare all three"])

        with st.expander("Advanced settings"):
            hc_max_iters = st.number_input("HC max iterations", min_value=1, value=100)
            sa_max_iters = st.number_input("SA max iterations", min_value=1, value=5000)
            ga_population = st.number_input("GA population size", min_value=2, value=10)
            ga_generations = st.number_input("GA max generations", min_value=1, value=200)

        run_seed = st.number_input("Run seed", min_value=0, value=42, step=1)
        run_clicked = st.button("Generate Timetable", type="primary", disabled=instance is None)

    if instance is None:
        st.info(
            "Upload courses.csv, enrollments.csv, and rooms.csv in the sidebar — "
            "or switch to synthetic demo data — then click **Generate Timetable**."
        )
        return

    st.subheader("Problem instance")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Exams", instance.num_exams)
    c2.metric("Students", instance.num_students)
    c3.metric("Rooms", instance.num_rooms)
    c4.metric("Time slots", instance.num_slots)

    hc_candidates = instance.num_exams * instance.num_slots * instance.num_rooms + (
        instance.num_exams * (instance.num_exams - 1) // 2
    )
    if hc_candidates > 3000:
        st.warning(
            "Hill-Climbing scores every shift and swap each round "
            f"(~{hc_candidates:,} candidates/round here, scaling with "
            "exams × slots × rooms, and each one's cost touches every student "
            "enrolled in the exam that moves) — at this size it can take a "
            "minute or more per run, with no progress shown until it finishes. "
            "Lower its max-iterations in Advanced settings if you want a faster, "
            "rougher answer."
        )

    params = {
        "hc_max_iters": int(hc_max_iters),
        "sa_max_iters": int(sa_max_iters),
        "ga_population": int(ga_population),
        "ga_generations": int(ga_generations),
    }

    if run_clicked:
        if mode == "Compare all three":
            results = {}
            progress = st.progress(0.0)
            for i, (name, algo) in enumerate(ALGORITHMS.items()):
                progress.progress(i / len(ALGORITHMS), text=f"Running {name}...")
                results[name] = algo(instance, random.Random(int(run_seed)), params)
            progress.progress(1.0, text="Done")
            progress.empty()
        else:
            with st.spinner(f"Running {mode}..."):
                results = {mode: ALGORITHMS[mode](instance, random.Random(int(run_seed)), params)}

        st.session_state["results"] = results
        st.session_state["solved_instance"] = instance
        st.session_state["solved_labels"] = labels
        st.session_state["solved_period_labels"] = period_labels

    if "results" not in st.session_state:
        return

    results = st.session_state["results"]
    solved_instance = st.session_state["solved_instance"]
    solved_labels = st.session_state["solved_labels"]
    solved_period_labels = st.session_state["solved_period_labels"]
    room_labels = solved_labels.room_ids if solved_labels else None
    student_labels = solved_labels.student_ids if solved_labels else None

    st.divider()
    st.subheader("Results")

    if len(results) > 1:
        render_comparison_charts(results)
        comparison_rows = [
            {
                "Algorithm": name,
                "Final cost": r.cost.total,
                "Hard violations": r.cost.hard,
                "Soft violations": r.cost.soft,
                "Iterations": r.iterations,
                "Time (s)": round(r.elapsed_seconds, 3),
            }
            for name, r in results.items()
        ]
        st.dataframe(comparison_rows, use_container_width=True)
        chosen = st.selectbox("Show timetable / violations for:", list(results.keys()))
    else:
        chosen = next(iter(results))

    result = results[chosen]
    cost = result.cost

    st.markdown(f"**{chosen}** — final cost **{cost.total}** (hard={cost.hard}, soft={cost.soft}), "
                f"{result.iterations} iterations, {result.elapsed_seconds:.2f}s")

    if cost.total == 0:
        st.success("Valid timetable — zero violations.")

    st.markdown("#### Timetable")
    st.caption(
        '"Day 2" is the 2nd exam day (not a calendar date); the "Time" '
        "column is which period of that day."
    )
    exam_rows = build_exam_list(solved_instance, result.assignment, room_labels, solved_period_labels)
    st.dataframe(exam_rows, use_container_width=True, hide_index=True)
    st.download_button(
        "Download timetable (CSV)",
        data=list_to_csv(exam_rows),
        file_name=f"timetable_{chosen.lower().replace(' ', '_')}.csv",
        mime="text/csv",
    )

    with st.expander("Grid view (day/period × room) — shows room utilization across the week"):
        grid_rows, _ = build_grid(solved_instance, result.assignment, room_labels, solved_period_labels)
        st.dataframe(grid_rows, use_container_width=True, hide_index=True)

    report = build_violation_report(
        solved_instance,
        result.assignment,
        room_labels=room_labels,
        student_labels=student_labels,
        period_labels=solved_period_labels,
    )
    st.markdown("#### Violations")
    if report.is_clean:
        st.success("No violations — this is a fully valid timetable.")
    else:
        if report.hard:
            with st.expander(f"Hard violations ({len(report.hard)})", expanded=True):
                for line in report.hard:
                    st.error(line, icon="⚠️")
        if report.soft:
            with st.expander(f"Soft violations ({len(report.soft)})"):
                for line in report.soft:
                    st.warning(line, icon="ℹ️")
        report_text = "Hard violations:\n" + "\n".join(report.hard) + "\n\nSoft violations:\n" + "\n".join(report.soft)
        st.download_button(
            "Download violations report (.txt)",
            data=report_text,
            file_name=f"violations_{chosen.lower().replace(' ', '_')}.txt",
            mime="text/plain",
        )


if __name__ == "__main__":
    main()

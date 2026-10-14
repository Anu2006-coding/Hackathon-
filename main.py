import csv
import math
import time
from pathlib import Path

import matplotlib.pyplot as plt


OUTPUT_FILE = "timetable.csv"


# --------------------------------------------------
# 1. READ INPUT
# --------------------------------------------------
def read_input():
    courses = [
        item.strip()
        for item in input(
            "Enter course names separated by commas (e.g. A,B,C,D): "
        ).split(",")
        if item.strip()
    ]

    if not courses or len(set(courses)) != len(courses):
        raise ValueError("Course names must be non-empty and unique.")

    n = len(courses)
    index = {course: i for i, course in enumerate(courses)}
    graph = [set() for _ in range(n)]

    print("\nEnter conflicting course pairs separated by commas.")
    print("Example: A-B,B-C,C-D")
    print("Press Enter if there are no conflicts.")

    raw = input("Conflict pairs: ").strip()

    if raw:
        for pair in raw.split(","):
            parts = pair.strip().split("-")

            if len(parts) != 2:
                raise ValueError(f"Invalid conflict pair: {pair}")

            a, b = [part.strip() for part in parts]

            if a not in index or b not in index:
                raise ValueError(
                    f"Unknown course in conflict pair: {pair}"
                )

            if a == b:
                raise ValueError(
                    f"A course cannot conflict with itself: {a}"
                )

            graph[index[a]].add(index[b])
            graph[index[b]].add(index[a])

    capacity = int(input("Maximum exams per time slot (R): "))

    if capacity < 1:
        raise ValueError("R must be at least 1.")

    return courses, graph, capacity


# --------------------------------------------------
# 2. GREEDY DSATUR SCHEDULING
# --------------------------------------------------
def greedy_dsatur(graph, capacity):
    n = len(graph)
    colors = [-1] * n
    slot_sizes = []

    while -1 in colors:
        uncolored = [v for v in range(n) if colors[v] == -1]

        # Select the vertex with highest saturation degree.
        # Break ties by choosing the highest-degree vertex.
        def priority(v):
            neighbor_colors = {
                colors[u] for u in graph[v] if colors[u] != -1
            }
            return len(neighbor_colors), len(graph[v])

        vertex = max(uncolored, key=priority)

        forbidden = {
            colors[u] for u in graph[vertex] if colors[u] != -1
        }

        assigned = False

        for color in range(len(slot_sizes)):
            if color not in forbidden and slot_sizes[color] < capacity:
                colors[vertex] = color
                slot_sizes[color] += 1
                assigned = True
                break

        if not assigned:
            colors[vertex] = len(slot_sizes)
            slot_sizes.append(1)

    return colors, len(slot_sizes)


# --------------------------------------------------
# 3. EXACT BACKTRACKING
# --------------------------------------------------
def can_color_with_k(graph, capacity, k):
    n = len(graph)
    colors = [-1] * n
    sizes = [0] * k

    def search(colored_count):
        if colored_count == n:
            return True

        uncolored = [v for v in range(n) if colors[v] == -1]

        # Dynamic DSatur ordering.
        def priority(v):
            saturation = len({
                colors[u] for u in graph[v] if colors[u] != -1
            })
            return saturation, len(graph[v])

        vertex = max(uncolored, key=priority)

        forbidden = {
            colors[u] for u in graph[vertex] if colors[u] != -1
        }

        # Try existing slots first, then unused slots.
        for color in range(k):
            if color in forbidden or sizes[color] >= capacity:
                continue

            colors[vertex] = color
            sizes[color] += 1

            if search(colored_count + 1):
                return True

            colors[vertex] = -1
            sizes[color] -= 1

            # Avoid symmetric empty-slot choices.
            if sizes[color] == 0:
                break

        return False

    if search(0):
        return colors
    return None


def exact_schedule(graph, capacity, upper_bound):
    n = len(graph)

    # At least ceil(n / capacity) slots are required.
    lower_bound = math.ceil(n / capacity)

    for k in range(lower_bound, upper_bound + 1):
        solution = can_color_with_k(graph, capacity, k)

        if solution is not None:
            return solution, k

    raise RuntimeError("No feasible schedule found.")


# --------------------------------------------------
# 4. DISPLAY AND SAVE TIMETABLE
# --------------------------------------------------
def print_schedule(courses, colors, slot_count, capacity, title):
    print(f"\n{title} ({slot_count} slots)")

    for slot in range(slot_count):
        assigned = [
            courses[i] for i, color in enumerate(colors)
            if color == slot
        ]

        print(
            f"Slot {slot + 1}: "
            + (", ".join(assigned) if assigned else "Empty")
        )

        if len(assigned) > capacity:
            raise RuntimeError("Slot capacity exceeded.")


def save_timetable(courses, colors, slot_count, capacity):
    with open(OUTPUT_FILE, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)

        writer.writerow(
            ["Time Slot"] +
            [f"Exam Position {i + 1}" for i in range(capacity)]
        )

        for slot in range(slot_count):
            assigned = [
                courses[i] for i, color in enumerate(colors)
                if color == slot
            ]

            row = [f"Slot {slot + 1}"] + assigned
            row += [""] * (capacity - len(assigned))
            writer.writerow(row)

    print("\nTimetable saved to:", Path(OUTPUT_FILE).resolve())


# --------------------------------------------------
# 5. VISUALIZE CONFLICT GRAPH AND TIMETABLE
# --------------------------------------------------
def visualize(courses, graph, colors, slot_count, capacity,
              greedy_time, exact_time):
    n = len(courses)
    fig, axes = plt.subplots(1, 3, figsize=(16, 5))

    # Conflict graph using circular positions.
    ax = axes[0]
    positions = {}

    for i in range(n):
        angle = 2 * math.pi * i / max(n, 1)
        positions[i] = (
            math.cos(angle),
            math.sin(angle)
        )

    for v in range(n):
        for u in graph[v]:
            if u > v:
                x1, y1 = positions[v]
                x2, y2 = positions[u]
                ax.plot([x1, x2], [y1, y2], color="gray", zorder=1)

    cmap = plt.get_cmap("tab20")

    for v in range(n):
        x, y = positions[v]
        ax.scatter(
            x, y, s=600,
            color=cmap(colors[v] % 20),
            edgecolors="black", zorder=2
        )
        ax.text(x, y, courses[v], ha="center", va="center", zorder=3)

    ax.set_title("Conflict Graph")
    ax.axis("off")

    # Exact timetable grid.
    ax = axes[1]
    table = []

    for slot in range(slot_count):
        assigned = [
            courses[i] for i, color in enumerate(colors)
            if color == slot
        ]
        row = assigned + [""] * (capacity - len(assigned))
        table.append(row)

    ax.axis("off")
    ax.set_title("Exact Timetable")

    display_table = ax.table(
        cellText=table,
        rowLabels=[f"Slot {i + 1}" for i in range(slot_count)],
        colLabels=[f"Position {i + 1}" for i in range(capacity)],
        cellLoc="center",
        loc="center"
    )
    display_table.auto_set_font_size(False)
    display_table.set_fontsize(8)
    display_table.scale(1, 1.6)

    # Algorithm runtime comparison.
    ax = axes[2]
    ax.bar(
        ["Greedy DSatur", "Exact Backtracking"],
        [greedy_time, exact_time]
    )
    ax.set_title("Execution Time")
    ax.set_ylabel("Seconds")
    ax.tick_params(axis="x", labelrotation=15)

    plt.tight_layout()
    plt.show()


# --------------------------------------------------
# 6. MAIN PROGRAM
# --------------------------------------------------
def main():
    try:
        courses, graph, capacity = read_input()

        start = time.perf_counter()
        greedy_colors, greedy_count = greedy_dsatur(
            graph, capacity
        )
        greedy_time = time.perf_counter() - start

        start = time.perf_counter()
        exact_colors, exact_count = exact_schedule(
            graph, capacity, greedy_count
        )
        exact_time = time.perf_counter() - start

        print_schedule(
            courses, greedy_colors, greedy_count, capacity,
            "Greedy DSatur timetable"
        )

        print_schedule(
            courses, exact_colors, exact_count, capacity,
            "Optimal timetable"
        )

        print("\nGreedy slot count:", greedy_count)
        print("Minimum slot count:", exact_count)
        print("Greedy is optimal:", greedy_count == exact_count)
        print(f"Greedy runtime: {greedy_time:.6f} seconds")
        print(f"Exact runtime:  {exact_time:.6f} seconds")

        save_timetable(
            courses, exact_colors, exact_count, capacity
        )

        visualize(
            courses, graph, exact_colors, exact_count, capacity,
            greedy_time, exact_time
        )

    except (ValueError, OSError, csv.Error, RuntimeError) as error:
        print("Error:", error)


if __name__ == "__main__":
    main()
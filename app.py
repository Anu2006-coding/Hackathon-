from flask import Flask, render_template, request, send_file
from pathlib import Path
from itertools import combinations
import csv
import io
import time

app = Flask(__name__)
MAX_COURSES = 18


# --------------------------------------------------
# 1. BUILD THE CONFLICT GRAPH
# --------------------------------------------------
def build_graph(courses, conflict_text):
    index = {course: i for i, course in enumerate(courses)}
    graph = [set() for _ in courses]

    for item in conflict_text.split(","):
        item = item.strip()
        if not item:
            continue

        parts = item.split("-")
        if len(parts) != 2:
            raise ValueError(
                f"Invalid conflict '{item}'. Use A-B format."
            )

        a, b = [part.strip() for part in parts]

        if a not in index or b not in index:
            raise ValueError(
                f"Conflict '{item}' contains an unknown course."
            )
        if a == b:
            raise ValueError("A course cannot conflict with itself.")

        u, v = index[a], index[b]
        graph[u].add(v)
        graph[v].add(u)

    return graph


# --------------------------------------------------
# 2. CHECK WHETHER A COURSE FITS IN A SLOT
# --------------------------------------------------
def can_assign(vertex, color, colors, graph, capacity):
    if sum(c == color for c in colors) >= capacity:
        return False

    for neighbor in graph[vertex]:
        if colors[neighbor] == color:
            return False

    return True


# --------------------------------------------------
# 3. GREEDY DSATUR ALGORITHM
# --------------------------------------------------
def greedy_dsatur(graph, capacity):
    n = len(graph)
    colors = [-1] * n

    for _ in range(n):
        uncolored = [v for v in range(n) if colors[v] == -1]

        if not uncolored:
            break

        def priority(v):
            saturation = len({
                colors[u] for u in graph[v] if colors[u] != -1
            })
            return saturation, len(graph[v]), -v

        vertex = max(uncolored, key=priority)

        color = 0
        while not can_assign(
            vertex, color, colors, graph, capacity
        ):
            color += 1

        colors[vertex] = color

    return colors, max(colors) + 1 if colors else 0


# --------------------------------------------------
# 4. EXACT BACKTRACKING: MINIMUM NUMBER OF SLOTS
# --------------------------------------------------
def exact_schedule(graph, capacity, upper_bound):
    n = len(graph)

    if n == 0:
        return [], 0

    lower_bound = max(
        1, (n + capacity - 1) // capacity
    )

    # Try each possible slot count, starting at the
    # theoretical capacity lower bound.
    for limit in range(lower_bound, upper_bound + 1):
        colors = [-1] * n
        slot_sizes = [0] * limit

        def search(assigned):
            if assigned == n:
                return True

            uncolored = [
                v for v in range(n) if colors[v] == -1
            ]

            def priority(v):
                saturation = len({
                    colors[u] for u in graph[v]
                    if colors[u] != -1
                })
                return saturation, len(graph[v]), -v

            vertex = max(uncolored, key=priority)

            # Symmetry breaking: only open the next unused
            # slot after trying all existing slots.
            used_colors = {
                c for c in colors if c != -1
            }
            max_used = max(used_colors, default=-1)

            for color in range(min(max_used + 2, limit)):
                if not can_assign(
                    vertex, color, colors, graph, capacity
                ):
                    continue

                colors[vertex] = color
                slot_sizes[color] += 1

                if search(assigned + 1):
                    return True

                colors[vertex] = -1
                slot_sizes[color] -= 1

            return False

        if search(0):
            return colors, limit

    # The greedy result is always a valid upper bound.
    return greedy_dsatur(graph, capacity)


# --------------------------------------------------
# 5. VALIDATE THE GENERATED TIMETABLE
# --------------------------------------------------
def validate_schedule(graph, colors, capacity):
    if len(colors) != len(graph):
        return False, "Some courses are missing."

    if any(c < 0 for c in colors):
        return False, "Some courses are not scheduled."

    sizes = {}
    for color in colors:
        sizes[color] = sizes.get(color, 0) + 1

    if any(size > capacity for size in sizes.values()):
        return False, "A slot exceeds the capacity."

    for v in range(len(graph)):
        for u in graph[v]:
            if colors[v] == colors[u]:
                return False, "Conflicting courses share a slot."

    return True, "All conflict and capacity constraints are satisfied."


def make_slots(courses, colors, count, capacity):
    return [
        {
            "name": f"Slot {slot + 1}",
            "courses": [
                courses[i] for i, color in enumerate(colors)
                if color == slot
            ],
            "count": sum(color == slot for color in colors),
            "capacity": capacity,
        }
        for slot in range(count)
    ]


# --------------------------------------------------
# 6. MAIN DASHBOARD
# --------------------------------------------------
@app.route("/", methods=["GET", "POST"])
def index():
    result = None
    error = None

    courses_text = "A,B,C,D,E"
    conflicts_text = "A-B,A-C,B-C,C-D,D-E"
    capacity_text = "2"

    if request.method == "POST":
        courses_text = request.form.get("courses", "").strip()
        conflicts_text = request.form.get("conflicts", "").strip()
        capacity_text = request.form.get("capacity", "2").strip()

        try:
            courses = [
                c.strip() for c in courses_text.split(",")
                if c.strip()
            ]

            if not courses:
                raise ValueError("Enter at least one course.")

            if len(courses) > MAX_COURSES:
                raise ValueError(
                    f"Use at most {MAX_COURSES} courses for this demo."
                )

            if len(set(courses)) != len(courses):
                raise ValueError("Course names must be unique.")

            if any("-" in c for c in courses):
                raise ValueError(
                    "Course names cannot contain hyphens."
                )

            capacity = int(capacity_text)
            if capacity < 1 or capacity > len(courses):
                raise ValueError(
                    "Capacity must be between 1 and the number of courses."
                )

            graph = build_graph(courses, conflicts_text)

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

            valid, message = validate_schedule(
                graph, exact_colors, capacity
            )
            if not valid:
                raise RuntimeError(message)

            result = {
                "course_count": len(courses),
                "conflict_count": sum(map(len, graph)) // 2,
                "capacity": capacity,
                "greedy_count": greedy_count,
                "exact_count": exact_count,
                "greedy_time": f"{greedy_time:.6f}",
                "exact_time": f"{exact_time:.6f}",
                "greedy_slots": make_slots(
                    courses, greedy_colors, greedy_count, capacity
                ),
                "exact_slots": make_slots(
                    courses, exact_colors, exact_count, capacity
                ),
                "valid": valid,
                "message": message,
                "greedy_optimal": greedy_count == exact_count,
            }

            # Prepare CSV download.
            output = io.StringIO()
            writer = csv.writer(output)
            writer.writerow(["Time Slot", "Courses", "Exam Count"])

            for slot in result["exact_slots"]:
                writer.writerow([
                    slot["name"],
                    ", ".join(slot["courses"]),
                    slot["count"],
                ])

            Path(__file__).with_name("timetable.csv").write_text(
                output.getvalue(), encoding="utf-8-sig"
            )

        except (ValueError, RuntimeError) as exc:
            error = str(exc)

    return render_template(
        "index.html",
        result=result,
        error=error,
        courses_text=courses_text,
        conflicts_text=conflicts_text,
        capacity_text=capacity_text,
    )


@app.route("/download")
def download():
    path = Path(__file__).with_name("timetable.csv")

    if not path.exists():
        return "Generate a timetable first.", 404

    return send_file(
        path,
        as_attachment=True,
        download_name="timetable.csv",
        mimetype="text/csv",
    )


if __name__ == "__main__":
    app.run(debug=True)
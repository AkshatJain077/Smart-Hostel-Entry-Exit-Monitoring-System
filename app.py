from flask import Flask, render_template, request

import sqlite3

app = Flask(__name__)

students_dict = {}

hostel_graph = {
    1: [(2, 4), (3, 2)],
    2: [(1, 4), (4, 3)],
    3: [(1, 2)],
    4: [(2, 3)]
}

from collections import deque

def bfs_inspection(start):
    visited = set()
    queue = deque()

    queue.append(start)
    visited.add(start)

    visited_rooms = []

    while queue:
        room = queue.popleft()
        visited_rooms.append(room)

        for neighbor in hostel_graph.get(room, []):
            if neighbor not in visited:
                visited.add(neighbor)
                queue.append(neighbor)

    return visited_rooms


import heapq

def dijkstra(start, target):
    pq = []
    heapq.heappush(pq, (0, start))

    distances = {node: float('inf') for node in hostel_graph}
    distances[start] = 0

    parent = {}

    while pq:
        current_dist, node = heapq.heappop(pq)

        for neighbor, weight in hostel_graph.get(node, []):
            distance = current_dist + weight

            if distance < distances[neighbor]:
                distances[neighbor] = distance
                parent[neighbor] = node
                heapq.heappush(pq, (distance, neighbor))

    # reconstruct path
    path = []
    curr = target

    while curr != start:
        path.append(curr)
        curr = parent.get(curr, start)

    path.append(start)
    path.reverse()

    return path, distances[target]


# Fine Function
from datetime import datetime

def calculate_fine(last_exit, entry_time):
    if last_exit is None:
        return 0

    fmt = "%Y-%m-%d %H:%M:%S"

    exit_time = datetime.strptime(last_exit, fmt)
    entry_time = datetime.strptime(entry_time, fmt)

    diff = (entry_time - exit_time).seconds / 3600  # hours

    if diff <= 1:
        return 50
    elif diff <= 2:
        return 100
    else:
        return 200

# -----------------------------
# Database Initialization
# -----------------------------
def init_db():
    conn = sqlite3.connect("hostel.db")
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS students (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            room INTEGER NOT NULL,
            inside INTEGER DEFAULT 1,
            last_entry TEXT,
            last_exit TEXT,
            fine INTEGER DEFAULT 0
        )
    """)

    conn.commit()
    conn.close()


def load_students():
    global students_dict

    conn = sqlite3.connect("hostel.db")
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM students")
    students = cursor.fetchall()

    conn.close()

    for student in students:
        students_dict[student[0]] = student


# -----------------------------
# Home Route
# -----------------------------
@app.route("/")
def home():
    total = len(students_dict)

    inside = sum(1 for s in students_dict.values() if s[3] == 1)
    outside = total - inside

    total_fine = sum(s[6] for s in students_dict.values())

    return render_template("home.html",
                           total=total,
                           inside=inside,
                           outside=outside,
                           total_fine=total_fine)


# -----------------------------
# Add Student Route
# -----------------------------
@app.route("/add", methods=["GET", "POST"])
def add_student():
    if request.method == "POST":
        student_id = request.form["id"]
        name = request.form["name"]
        room = request.form["room"]

        conn = sqlite3.connect("hostel.db")
        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO students (id, name, room, inside)
            VALUES (?, ?, ?, 1)
        """, (student_id, name, room))

        conn.commit()
        conn.close()

        students_dict[int(student_id)] = (
            int(student_id),
            name,
            int(room),
            1,
            None,
            None,
            0
        )

        return "Student Added Successfully!"

    return render_template("add_student.html")


@app.route("/view")
def view_students():
    conn = sqlite3.connect("hostel.db")
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM students")
    students = cursor.fetchall()

    conn.close()

    return render_template("view_students.html", students=students)


@app.route("/update", methods=["GET", "POST"])
def update_status():
    if request.method == "POST":
        student_id = int(request.form["id"])
        action = request.form["action"]

        conn = sqlite3.connect("hostel.db")
        cursor = conn.cursor()

        if action == "entry":
            cursor.execute("""
                UPDATE students 
                SET inside = 1, last_entry = datetime('now')
                WHERE id = ?
            """, (student_id,))

            # 🔥 Get current time
            conn.commit()

            cursor.execute("SELECT last_exit FROM students WHERE id = ?", (student_id,))
            last_exit = cursor.fetchone()[0]

            cursor.execute("SELECT last_entry FROM students WHERE id = ?", (student_id,))
            last_entry = cursor.fetchone()[0]

            fine = calculate_fine(last_exit, last_entry)

            cursor.execute("""
                UPDATE students SET fine = fine + ?
                WHERE id = ?
            """, (fine, student_id))

            # 🔥 Update dictionary
            student = list(students_dict[student_id])
            student[3] = 1
            student[6] += fine
            students_dict[student_id] = tuple(student)

        else:
            cursor.execute("""
                UPDATE students 
                SET inside = 0, last_exit = datetime('now')
                WHERE id = ?
            """, (student_id,))

            # 🔥 Update dictionary
            student = list(students_dict[student_id])
            student[3] = 0  # inside = 0
            students_dict[student_id] = tuple(student)

        conn.commit()
        conn.close()

        return "Status Updated Successfully!"

    return render_template("update.html")


@app.route("/violators")
def show_violators():
    violators = []

    for student_id, student in students_dict.items():
        if student[3] == 0:   # inside column
            violators.append(student)

    return render_template("violators.html", students=violators)


@app.route("/inspect")
def inspect_hostel():
    rooms_visited = bfs_inspection(1)

    violators = []

    for student in students_dict.values():
        if student[3] == 0:  # outside
            violators.append(student)

    return render_template("inspect.html", rooms=rooms_visited, students=violators)


@app.route("/path/<int:room>")
def get_path(room):
    path, cost = dijkstra(1, room)
    return render_template("path.html", path=path, cost=cost)


@app.route("/clear_fine/<int:student_id>")
def clear_fine(student_id):

    conn = sqlite3.connect("hostel.db")
    cursor = conn.cursor()

    cursor.execute("""
        UPDATE students SET fine = 0
        WHERE id = ?
    """, (student_id,))

    conn.commit()
    conn.close()

    # 🔥 Update dictionary
    student = list(students_dict[student_id])
    student[6] = 0   # fine index
    students_dict[student_id] = tuple(student)

    return "Fine Cleared Successfully!"


# -----------------------------
# Run Server
# -----------------------------
if __name__ == "__main__":
    init_db()
    load_students()
    app.run(debug=True)
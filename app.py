# app.py
from flask import Flask, render_template, request, redirect, url_for, flash, session as flask_session
import sqlite3
import qrcode
import os
import uuid
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = "replace_this_with_a_random_secret"

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATABASE = os.path.join(BASE_DIR, 'attendance.db')
STATIC_QR_DIR = os.path.join(BASE_DIR, "static")
os.makedirs(STATIC_QR_DIR, exist_ok=True)

def get_db():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    with get_db() as conn:
        # students: registered students
        conn.execute('''CREATE TABLE IF NOT EXISTS students (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            name TEXT NOT NULL,
                            roll TEXT NOT NULL UNIQUE,
                            password TEXT NOT NULL
                        )''')
        # subjects: subject rows linked to student
        conn.execute('''CREATE TABLE IF NOT EXISTS subjects (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            student_id INTEGER NOT NULL,
                            subject_name TEXT NOT NULL,
                            FOREIGN KEY(student_id) REFERENCES students(id)
                        )''')
        # teachers
        conn.execute('''CREATE TABLE IF NOT EXISTS teachers (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            name TEXT NOT NULL,
                            username TEXT NOT NULL UNIQUE,
                            password TEXT NOT NULL
                        )''')
        # sessions: QR sessions per subject (teacher creates)
        conn.execute('''CREATE TABLE IF NOT EXISTS sessions (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            subject_name TEXT NOT NULL,
                            token TEXT NOT NULL UNIQUE,
                            created_at TEXT NOT NULL,
                            active INTEGER NOT NULL DEFAULT 1
                        )''')
        # attendance: records
        conn.execute('''CREATE TABLE IF NOT EXISTS attendance (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            student_id INTEGER NOT NULL,
                            session_id INTEGER NOT NULL,
                            timestamp TEXT NOT NULL,
                            FOREIGN KEY(student_id) REFERENCES students(id),
                            FOREIGN KEY(session_id) REFERENCES sessions(id)
                        )''')
        # ensure at least one teacher (username:admin, password:admin) — change in production
        cur = conn.execute("SELECT COUNT(*) as c FROM teachers")
        if cur.fetchone()["c"] == 0:
            conn.execute("INSERT INTO teachers (name, username, password) VALUES (?, ?, ?)",
                         ("Admin", "admin", generate_password_hash("admin")))
    print("DB initialized (attendance.db)")

init_db()

# ---------- Helper functions ----------
def query_one(query, params=()):
    with get_db() as conn:
        cur = conn.execute(query, params)
        return cur.fetchone()

def query_all(query, params=()):
    with get_db() as conn:
        cur = conn.execute(query, params)
        return cur.fetchall()

def execute(query, params=()):
    with get_db() as conn:
        cur = conn.execute(query, params)
        conn.commit()
        return cur.lastrowid

# ---------- Public routes ----------
@app.route('/')
def index():
    return render_template('index.html')

# Student registration: student chooses number of subjects and names
@app.route('/student/register', methods=['GET', 'POST'])
def student_register():
    if request.method == 'POST':
        name = request.form['name'].strip()
        roll = request.form['roll'].strip()
        password = request.form['password']
        try:
            hashed = generate_password_hash(password)
            student_id = execute("INSERT INTO students (name, roll, password) VALUES (?, ?, ?)",
                                 (name, roll, hashed))
        except sqlite3.IntegrityError:
            flash("Roll number already registered. Use different roll or login.")
            return redirect(url_for('student_register'))

        # store subjects
        subj_count = int(request.form.get('subject_count', 0))
        for i in range(1, subj_count+1):
            sname = request.form.get(f"subject_{i}", "").strip()
            if sname:
                execute("INSERT INTO subjects (student_id, subject_name) VALUES (?, ?)", (student_id, sname))
        flash("Registered successfully. Now login.")
        return redirect(url_for('student_login'))

    return render_template('student_register.html')

# Student login
@app.route('/student/login', methods=['GET', 'POST'])
def student_login():
    if request.method == 'POST':
        roll = request.form['roll'].strip()
        password = request.form['password']
        student = query_one("SELECT * FROM students WHERE roll = ?", (roll,))
        if student and check_password_hash(student['password'], password):
            flask_session.clear()
            flask_session['student_id'] = student['id']
            flask_session['student_name'] = student['name']
            flash("Logged in as student.")
            return redirect(url_for('student_dashboard'))
        else:
            flash("Invalid roll or password.")
    return render_template('student_login.html')

# Teacher login
@app.route('/teacher/login', methods=['GET', 'POST'])
def teacher_login():
    if request.method == 'POST':
        username = request.form['username'].strip()
        password = request.form['password']
        teacher = query_one("SELECT * FROM teachers WHERE username = ?", (username,))
        if teacher and check_password_hash(teacher['password'], password):
            flask_session.clear()
            flask_session['teacher_id'] = teacher['id']
            flask_session['teacher_name'] = teacher['name']
            flash("Logged in as teacher.")
            return redirect(url_for('teacher_dashboard'))
        else:
            flash("Invalid credentials.")
    return render_template('teacher_login.html')

@app.route('/logout')
def logout():
    flask_session.clear()
    flash("Logged out.")
    return redirect(url_for('index'))

# Student dashboard: shows their subjects and attendance summary
@app.route('/student/dashboard')
def student_dashboard():
    sid = flask_session.get('student_id')
    if not sid:
        flash("Please login first.")
        return redirect(url_for('student_login'))

    student = query_one("SELECT * FROM students WHERE id = ?", (sid,))
    subjects = query_all("SELECT subject_name FROM subjects WHERE student_id = ?", (sid,))

    # For each subject, compute total sessions and attended sessions
    report = []
    for s in subjects:
        subj = s['subject_name']
        total_sessions = query_one("SELECT COUNT(*) as c FROM sessions WHERE subject_name = ?", (subj,))['c']
        attended = query_one("""SELECT COUNT(*) as c FROM attendance
                                 JOIN sessions ON attendance.session_id = sessions.id
                                 WHERE attendance.student_id = ? AND sessions.subject_name = ?""",
                              (sid, subj))['c']
        pct = (attended / total_sessions * 100) if total_sessions > 0 else None
        report.append({
            'subject': subj,
            'total': total_sessions,
            'attended': attended,
            'percent': round(pct, 2) if pct is not None else 'N/A'
        })

    return render_template('student_dashboard.html', student=student, report=report)

# Teacher dashboard: generate QR, view sessions, and view attendance table
@app.route('/teacher/dashboard')
def teacher_dashboard():
    if not flask_session.get('teacher_id'):
        flash("Please login as teacher.")
        return redirect(url_for('teacher_login'))

    # list recent sessions
    sessions = query_all("SELECT * FROM sessions ORDER BY id DESC LIMIT 50")
    # prepare table: list of all students and all distinct subjects in the DB
    students = query_all("SELECT * FROM students ORDER BY roll")
    subjects = query_all("SELECT DISTINCT subject_name FROM subjects")
    # convert attendance counts by student+subject
    table = []
    subject_names = [s['subject_name'] for s in subjects]
    for st in students:
        row = {'student': st['name'], 'roll': st['roll'], 'by_subject': {}}
        for subj in subject_names:
            total_sessions = query_one("SELECT COUNT(*) as c FROM sessions WHERE subject_name = ?", (subj,))['c']
            attended = query_one("""SELECT COUNT(*) as c FROM attendance
                                    JOIN sessions ON attendance.session_id = sessions.id
                                    WHERE attendance.student_id = ? AND sessions.subject_name = ?""",
                                 (st['id'], subj))['c']
            pct = (attended / total_sessions * 100) if total_sessions > 0 else None
            row['by_subject'][subj] = {
                'attended': attended,
                'total': total_sessions,
                'percent': round(pct, 2) if pct is not None else 'N/A'
            }
        table.append(row)

    return render_template('teacher_dashboard.html', sessions=sessions, subjects=subject_names, table=table)

# Teacher action: create a new session (subject + QR)
@app.route('/teacher/create_session', methods=['POST'])
def teacher_create_session():
    if not flask_session.get('teacher_id'):
        flash("Please login as teacher.")
        return redirect(url_for('teacher_login'))

    subject = request.form.get('subject').strip()
    if not subject:
        flash("Enter subject name.")
        return redirect(url_for('teacher_dashboard'))

    token = str(uuid.uuid4())
    created_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    session_id = execute("INSERT INTO sessions (subject_name, token, created_at, active) VALUES (?, ?, ?, ?)",
                         (subject, token, created_at, 1))
    # create QR image file
    qr_text = url_for('mark_attendance', _external=True) + f"?token={token}"
    img = qrcode.make(qr_text)
    fname = f"qr_{session_id}.png"
    img.save(os.path.join(STATIC_QR_DIR, fname))
    flash("Session created and QR generated.")
    return redirect(url_for('teacher_dashboard'))

# Teacher action: end a session (deactivate)
@app.route('/teacher/end_session/<int:session_id>', methods=['POST'])
def teacher_end_session(session_id):
    if not flask_session.get('teacher_id'):
        flash("Please login as teacher.")
        return redirect(url_for('teacher_login'))
    execute("UPDATE sessions SET active = 0 WHERE id = ?", (session_id,))
    flash("Session ended.")
    return redirect(url_for('teacher_dashboard'))

# Mark attendance — this route is only accessible via QR token.
# It requires the student to be logged in. After scanning the QR,
# the student's browser will open this URL with token param.
@app.route('/mark_attendance', methods=['GET', 'POST'])
def mark_attendance():
    token = request.args.get('token') or request.form.get('token')
    if not token:
        flash("Invalid QR. No token present.")
        return redirect(url_for('index'))

    srow = query_one("SELECT * FROM sessions WHERE token = ? AND active = 1", (token,))
    if not srow:
        flash("This session is invalid or has ended.")
        return redirect(url_for('index'))

    # student must be logged in
    sid = flask_session.get('student_id')
    if not sid:
        # show page asking to login, but keep token so after login they can mark
        return render_template('mark_require_login.html', token=token)

    # GET shows confirmation page with subject & token
    if request.method == 'GET':
        return render_template('mark_confirm.html', session=srow)

    # POST tries to mark attendance
    # Prevent duplicate marking (one record per student per session)
    exists = query_one("SELECT COUNT(*) as c FROM attendance WHERE student_id = ? AND session_id = ?",
                       (sid, srow['id']))['c']
    if exists > 0:
        flash("You have already marked attendance for this session.")
        return redirect(url_for('student_dashboard'))

    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    execute("INSERT INTO attendance (student_id, session_id, timestamp) VALUES (?, ?, ?)",
            (sid, srow['id'], timestamp))

    flash("Attendance marked successfully.")
    return redirect(url_for('student_dashboard'))

# small helper to populate subjects from student's entry page (AJAX optional)
@app.route('/student/subjects/<int:student_id>')
def get_student_subjects(student_id):
    subjects = query_all("SELECT subject_name FROM subjects WHERE student_id = ?", (student_id,))
    return {"subjects": [s['subject_name'] for s in subjects]}

if __name__ == '__main__':
    app.run(debug=True)

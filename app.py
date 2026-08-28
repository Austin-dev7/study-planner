from flask import Flask, render_template, request, redirect, url_for, session, jsonify, send_from_directory, flash
from datetime import datetime, timedelta
import calendar
import os
import uuid
import secrets
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash
from flask_wtf.csrf import CSRFProtect
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

# ===== Database Backend Selection =====
DATABASE_URL = os.environ.get('DATABASE_URL', '')

if DATABASE_URL:
    import psycopg2
    import psycopg2.extras
    DB_IS_POSTGRES = True
else:
    import sqlite3
    DB_IS_POSTGRES = False

app = Flask(__name__)

if os.environ.get('SECRET_KEY'):
    app.secret_key = os.environ['SECRET_KEY']
else:
    current_is_production = os.environ.get('FLASK_ENV') == 'production' or os.environ.get('VERCEL') == '1'
    if current_is_production:
        raise RuntimeError('SECRET_KEY environment variable must be set in production.')
    app.secret_key = secrets.token_hex(32)

# ===== Security Configuration =====
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
app.config['SESSION_COOKIE_SECURE'] = os.environ.get('COOKIE_SECURE', '0') == '1'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024

csrf = CSRFProtect(app)

limiter = Limiter(
    get_remote_address,
    app=app,
    default_limits=['200 per day', '60 per hour'],
    storage_uri='memory://',
)

# ===== Security Headers =====
@app.after_request
def set_security_headers(response):
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'SAMEORIGIN'
    response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
    response.headers['X-XSS-Protection'] = '1; mode=block'
    response.headers['Permissions-Policy'] = 'geolocation=(), microphone=(), camera=()'
    response.headers['Content-Security-Policy'] = (
        "default-src 'self'; "
        "script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net https://cdnjs.cloudflare.com; "
        "style-src 'self' 'unsafe-inline' https://cdnjs.cloudflare.com; "
        "font-src 'self' https://cdnjs.cloudflare.com data:; "
        "img-src 'self' data:; "
        "connect-src 'self'"
    )
    return response

# Upload folder for reminder sounds
UPLOAD_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static', 'uploads', 'sounds')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
ALLOWED_EXTENSIONS = {'mp3', 'wav', 'ogg', 'm4a', 'aac'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# ===== Database wrapper =====
class DB:
    def __init__(self, conn):
        self.conn = conn
        global DB_IS_POSTGRES
        self.is_postgres = DB_IS_POSTGRES

    def execute(self, sql, params=None):
        if self.is_postgres:
            sql = sql.replace("strftime('%Y-%m', due_date)", 'LEFT(due_date, 7)')
            sql = sql.replace("date('now', '-7 days')", "(CURRENT_DATE - INTERVAL '7 days')")
            sql = sql.replace("datetime(reminder_time) <= datetime(?)", "reminder_time::timestamp <= %s::timestamp")
            sql = sql.replace("datetime(reminder_time) >= datetime(?, '-5 minutes')", "reminder_time::timestamp >= %s::timestamp - INTERVAL '5 minutes'")
            stripped = sql.lstrip().upper()
            if stripped.startswith('INSERT') and ' RETURNING ' not in stripped:
                sql = sql.rstrip().rstrip(';') + ' RETURNING id'
            sql = sql.replace('?', '%s')
            cur = self.conn.cursor()
            if params:
                cur.execute(sql, params)
            else:
                cur.execute(sql)
            return cur
        else:
            cur = self.conn.cursor()
            if params:
                cur.execute(sql, params)
            else:
                cur.execute(sql)
            return cur

    def cursor(self):
        return self.conn.cursor()

    def lastrowid(self, cursor):
        if self.is_postgres:
            row = cursor.fetchone()
            return row['id'] if row else None
        return cursor.lastrowid

    def commit(self):
        self.conn.commit()

    def close(self):
        self.conn.close()

def get_db():
    if DB_IS_POSTGRES:
        conn = psycopg2.connect(DATABASE_URL, cursor_factory=psycopg2.extras.RealDictCursor)
    else:
        conn = sqlite3.connect('study_planner.db')
        conn.row_factory = sqlite3.Row
    return DB(conn)

def init_db():
    conn = get_db()
    cursor = conn.cursor()

    if DB_IS_POSTGRES:
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id SERIAL PRIMARY KEY,
                email VARCHAR(255) UNIQUE NOT NULL,
                password TEXT NOT NULL,
                name VARCHAR(255) DEFAULT 'Student',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS tasks (
                id SERIAL PRIMARY KEY,
                user_id INTEGER NOT NULL REFERENCES users (id),
                title TEXT NOT NULL,
                subject TEXT NOT NULL,
                priority TEXT NOT NULL,
                due_date TEXT NOT NULL,
                description TEXT,
                status TEXT DEFAULT 'pending',
                reminder_time TEXT,
                reminder_sound TEXT,
                reminder_notified INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS study_sessions (
                id SERIAL PRIMARY KEY,
                user_id INTEGER NOT NULL REFERENCES users (id),
                subject TEXT NOT NULL,
                duration INTEGER NOT NULL,
                date TEXT NOT NULL
            )
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS subjects (
                id SERIAL PRIMARY KEY,
                user_id INTEGER NOT NULL REFERENCES users (id),
                name TEXT NOT NULL,
                color TEXT DEFAULT '#7C3AED'
            )
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS notes (
                id SERIAL PRIMARY KEY,
                user_id INTEGER NOT NULL REFERENCES users (id),
                title TEXT NOT NULL,
                content TEXT DEFAULT '',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS reminder_sounds (
                id SERIAL PRIMARY KEY,
                user_id INTEGER NOT NULL REFERENCES users (id),
                name TEXT NOT NULL,
                file_path TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
    else:
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email TEXT UNIQUE NOT NULL,
                password TEXT NOT NULL,
                name TEXT DEFAULT 'Student',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                title TEXT NOT NULL,
                subject TEXT NOT NULL,
                priority TEXT NOT NULL,
                due_date TEXT NOT NULL,
                description TEXT,
                status TEXT DEFAULT 'pending',
                reminder_time TEXT,
                reminder_sound TEXT,
                reminder_notified INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users (id)
            )
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS study_sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                subject TEXT NOT NULL,
                duration INTEGER NOT NULL,
                date TEXT NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users (id)
            )
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS subjects (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                name TEXT NOT NULL,
                color TEXT DEFAULT '#7C3AED',
                FOREIGN KEY (user_id) REFERENCES users (id)
            )
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS notes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                title TEXT NOT NULL,
                content TEXT DEFAULT '',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users (id)
            )
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS reminder_sounds (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                name TEXT NOT NULL,
                file_path TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users (id)
            )
        ''')

    if not DB_IS_POSTGRES:
        try:
            cursor.execute('SELECT reminder_time FROM tasks LIMIT 1')
        except sqlite3.OperationalError:
            cursor.execute('ALTER TABLE tasks ADD COLUMN reminder_time TEXT')
            cursor.execute('ALTER TABLE tasks ADD COLUMN reminder_sound TEXT')
            cursor.execute('ALTER TABLE tasks ADD COLUMN reminder_notified INTEGER DEFAULT 0')

    conn.commit()
    conn.close()

init_db()

def is_hashed(password):
    return password.startswith(('scrypt:', 'pbkdf2:', 'sha256:'))

def migrate_plaintext_passwords():
    conn = get_db()
    users = conn.execute('SELECT id, password FROM users').fetchall()
    for u in users:
        if not is_hashed(u['password']):
            hashed = generate_password_hash(u['password'])
            conn.execute('UPDATE users SET password=? WHERE id=?', (hashed, u['id']))
    conn.commit()
    conn.close()

migrate_plaintext_passwords()

# ===== Demo Account Helpers =====
DEMO_EMAIL = 'demo@studyplanner.app'
DEMO_PASSWORD = 'demo123'

def ensure_demo_user():
    conn = get_db()
    user = conn.execute('SELECT * FROM users WHERE email = ?', (DEMO_EMAIL,)).fetchone()
    if not user:
        hashed = generate_password_hash(DEMO_PASSWORD)
        cursor = conn.execute('INSERT INTO users (email, password, name) VALUES (?, ?, ?)', (DEMO_EMAIL, hashed, 'Demo Student'))
        user_id = conn.lastrowid(cursor)
        conn.commit()
        sample_subjects = [
            ('Mathematics', '#7C3AED'),
            ('Computer Science', '#3B82F6'),
            ('Physics', '#10B981'),
            ('History', '#F59E0B')
        ]
        for name, color in sample_subjects:
            conn.execute('INSERT INTO subjects (user_id, name, color) VALUES (?, ?, ?)', (user_id, name, color))
        today = datetime.now()
        sample_tasks = [
            ('Complete Calculus Assignment', 'Mathematics', 'high', (today + timedelta(days=1)).strftime('%Y-%m-%d'), 'Chapter 5 problems 1-20', 'pending'),
            ('Read Chapter 3 - Algorithms', 'Computer Science', 'medium', (today + timedelta(days=2)).strftime('%Y-%m-%d'), 'Focus on sorting algorithms', 'in_progress'),
            ('Physics Lab Report', 'Physics', 'high', today.strftime('%Y-%m-%d'), 'Write up the pendulum experiment results', 'pending'),
            ('Study for History Exam', 'History', 'medium', (today + timedelta(days=5)).strftime('%Y-%m-%d'), 'Review WWI and WWII timelines', 'pending'),
            ('Watch Lecture Video', 'Computer Science', 'low', (today - timedelta(days=1)).strftime('%Y-%m-%d'), 'Data structures overview', 'completed'),
            ('Practice Problem Set', 'Mathematics', 'medium', (today - timedelta(days=2)).strftime('%Y-%m-%d'), 'Integration by parts', 'completed'),
        ]
        for title, subject, priority, due_date, desc, status in sample_tasks:
            conn.execute('INSERT INTO tasks (user_id, title, subject, priority, due_date, description, status) VALUES (?, ?, ?, ?, ?, ?, ?)', (user_id, title, subject, priority, due_date, desc, status))
        for i in range(7):
            date = (today - timedelta(days=i)).strftime('%Y-%m-%d')
            duration = [45, 60, 30, 90, 45, 120, 60][i]
            subject = ['Mathematics', 'Computer Science', 'Physics', 'History', 'Mathematics', 'Computer Science', 'Physics'][i]
            conn.execute('INSERT INTO study_sessions (user_id, subject, duration, date) VALUES (?, ?, ?, ?)', (user_id, subject, duration, date))
        sample_notes = [
            ('Integration Techniques', 'Key formulas:\n- Integration by parts\n- u-substitution\n- Partial fractions'),
            ('Sorting Algorithms Summary', 'QuickSort: O(n log n) avg\nMergeSort: O(n log n) guaranteed\nBubbleSort: O(n squared) - avoid'),
            ('Study Schedule Template', 'Morning: 2 hours Math\nAfternoon: 1.5 hours CS\nEvening: Review and notes'),
        ]
        for title, content in sample_notes:
            conn.execute('INSERT INTO notes (user_id, title, content) VALUES (?, ?, ?)', (user_id, title, content))
        conn.commit()
    conn.close()

# ===== Routes =====

@app.route('/')
def index():
    if 'user_id' in session:
        return redirect(url_for('dashboard'))
    return render_template('landing.html')

@app.route('/demo')
def demo_login():
    ensure_demo_user()
    conn = get_db()
    user = conn.execute('SELECT * FROM users WHERE email = ?', (DEMO_EMAIL,)).fetchone()
    conn.close()
    if user:
        session.clear()
        session['user_id'] = user['id']
        session['user_name'] = user['name']
        flash('Welcome to the demo account! All data resets when the server restarts.', 'info')
        return redirect(url_for('dashboard'))
    flash('Demo account unavailable. Please register.', 'error')
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
@limiter.limit('10 per minute')
def login():
    if request.method == 'POST':
        email = request.form['email'].strip().lower()
        password = request.form['password'].strip()
        if not email or not password:
            return render_template('login.html', error='Email and password are required')
        conn = get_db()
        user = conn.execute('SELECT * FROM users WHERE email = ?', (email,)).fetchone()
        conn.close()
        if user:
            stored = user['password']
            valid = check_password_hash(stored, password) if is_hashed(stored) else (stored == password)
            if valid:
                session.clear()
                session['user_id'] = user['id']
                session['user_name'] = user['name']
                return redirect(url_for('dashboard'))
        return render_template('login.html', error='Invalid email or password')
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        email = request.form['email'].strip().lower()
        password = request.form['password']
        name = request.form.get('name', 'Student')
        if not email or not password:
            return render_template('login.html', error='Email and password are required', tab='register')
        if len(password) < 6:
            return render_template('login.html', error='Password must be at least 6 characters', tab='register')
        conn = get_db()
        try:
            hashed = generate_password_hash(password)
            conn.execute('INSERT INTO users (email, password, name) VALUES (?, ?, ?)', (email, hashed, name))
            conn.commit()
            conn.close()
            flash('Account created! Please log in.', 'success')
            return redirect(url_for('login'))
        except Exception:
            conn.close()
            return render_template('login.html', error='Email already exists', tab='register')
    return redirect(url_for('login'))

@app.route('/logout')
def logout():
    session.clear()
    flash('You have been logged out.', 'info')
    return redirect(url_for('index'))

@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    user_id = session['user_id']
    conn = get_db()
    today = datetime.now().strftime('%Y-%m-%d')
    tasks_today = conn.execute('SELECT COUNT(*) as count FROM tasks WHERE user_id = ? AND due_date = ?', (user_id, today)).fetchone()['count']
    tasks_completed = conn.execute('SELECT COUNT(*) as count FROM tasks WHERE user_id = ? AND status = ?', (user_id, 'completed')).fetchone()['count']
    total_tasks = conn.execute('SELECT COUNT(*) as count FROM tasks WHERE user_id = ?', (user_id,)).fetchone()['count']
    study_hours = conn.execute('SELECT SUM(duration) as total FROM study_sessions WHERE user_id = ?', (user_id,)).fetchone()['total'] or 0
    study_hours = round(study_hours / 60, 1)
    subjects_count = conn.execute('SELECT COUNT(*) as count FROM subjects WHERE user_id = ?', (user_id,)).fetchone()['count']
    task_subjects_count = conn.execute('SELECT COUNT(DISTINCT subject) as count FROM tasks WHERE user_id = ? AND subject IS NOT NULL AND subject != ?', (user_id, '')).fetchone()['count']
    subjects_count = subjects_count + task_subjects_count
    upcoming_tasks = conn.execute('SELECT * FROM tasks WHERE user_id = ? AND status != ? ORDER BY due_date ASC LIMIT 5', (user_id, 'completed')).fetchall()
    overdue_count = conn.execute('SELECT COUNT(*) as count FROM tasks WHERE user_id = ? AND status != ? AND due_date < ?', (user_id, 'completed', today)).fetchone()['count']
    subjects = conn.execute('SELECT * FROM subjects WHERE user_id = ?', (user_id,)).fetchall()
    task_status = conn.execute('SELECT status, COUNT(*) as count FROM tasks WHERE user_id = ? GROUP BY status', (user_id,)).fetchall()
    status_map = {'pending': 0, 'in_progress': 0, 'completed': 0}
    for row in task_status:
        if row['status'] in status_map:
            status_map[row['status']] = row['count']
    focus_data = conn.execute("SELECT date, SUM(duration) as total FROM study_sessions WHERE user_id = ? AND date >= date('now', '-7 days') GROUP BY date ORDER BY date", (user_id,)).fetchall()
    focus_map = {row['date']: row['total'] for row in focus_data}
    daily_avg = None
    if focus_data:
        total_minutes = sum(row['total'] for row in focus_data)
        daily_avg = round(total_minutes / 7 / 60, 1)
    focus_labels = []
    focus_values = []
    for i in range(6, -1, -1):
        day = datetime.now() - timedelta(days=i)
        focus_labels.append(day.strftime('%a'))
        key = day.strftime('%Y-%m-%d')
        total = focus_map.get(key, 0)
        focus_values.append(round(total / 60, 1) if total else 0)
    conn.close()
    return render_template('dashboard.html', user_name=session.get('user_name', 'Student'), tasks_today=tasks_today, tasks_completed=tasks_completed, total_tasks=total_tasks, overdue_count=overdue_count, study_hours=study_hours, subjects_count=subjects_count, upcoming_tasks=upcoming_tasks, subjects=subjects, task_status=status_map, focus_data=focus_map, daily_avg=daily_avg, focus_labels=focus_labels, focus_values=focus_values)

@app.route('/tasks')
def tasks():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    user_id = session['user_id']
    filter_status = request.args.get('status', 'all')
    conn = get_db()
    if filter_status == 'all':
        tasks_list = conn.execute('SELECT * FROM tasks WHERE user_id = ? ORDER BY due_date ASC', (user_id,)).fetchall()
    else:
        tasks_list = conn.execute('SELECT * FROM tasks WHERE user_id = ? AND status = ? ORDER BY due_date ASC', (user_id, filter_status)).fetchall()
    conn.close()
    return render_template('tasks.html', tasks=tasks_list, current_filter=filter_status)

@app.route('/add_task', methods=['GET', 'POST'])
def add_task():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    if request.method == 'POST':
        user_id = session['user_id']
        title = request.form['title']
        subject = request.form['subject']
        priority = request.form['priority']
        due_date = request.form['due_date']
        description = request.form.get('description', '')
        reminder_time = request.form.get('reminder_time', '')
        reminder_sound = request.form.get('reminder_sound', '')
        custom_subject = request.form.get('custom_subject', '').strip()
        if custom_subject and not subject:
            subject = custom_subject
            conn_ck = get_db()
            existing = conn_ck.execute('SELECT id FROM subjects WHERE user_id = ? AND name = ?', (user_id, subject)).fetchone()
            if not existing:
                conn_ck.execute('INSERT INTO subjects (user_id, name) VALUES (?, ?)', (user_id, subject))
                conn_ck.commit()
            conn_ck.close()
        conn = get_db()
        conn.execute('INSERT INTO tasks (user_id, title, subject, priority, due_date, description, reminder_time, reminder_sound) VALUES (?, ?, ?, ?, ?, ?, ?, ?)', (user_id, title, subject, priority, due_date, description, reminder_time if reminder_time else None, reminder_sound if reminder_sound else None))
        conn.commit()
        conn.close()
        flash('Task added successfully!', 'success')
        return redirect(url_for('tasks'))
    conn = get_db()
    subjects = conn.execute('SELECT * FROM subjects WHERE user_id = ?', (session['user_id'],)).fetchall()
    sounds = conn.execute('SELECT * FROM reminder_sounds WHERE user_id = ?', (session['user_id'],)).fetchall()
    conn.close()
    return render_template('add_task.html', subjects=subjects, sounds=sounds)

@app.route('/edit_task/<int:task_id>', methods=['GET', 'POST'])
def edit_task(task_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    user_id = session['user_id']
    conn = get_db()
    task = conn.execute('SELECT * FROM tasks WHERE id = ? AND user_id = ?', (task_id, user_id)).fetchone()
    if not task:
        conn.close()
        flash('Task not found.', 'error')
        return redirect(url_for('tasks'))
    if request.method == 'POST':
        title = request.form['title']
        subject = request.form['subject']
        priority = request.form['priority']
        due_date = request.form['due_date']
        description = request.form.get('description', '')
        reminder_time = request.form.get('reminder_time', '')
        reminder_sound = request.form.get('reminder_sound', '')
        custom_subject = request.form.get('custom_subject', '').strip()
        if custom_subject and not subject:
            subject = custom_subject
            existing = conn.execute('SELECT id FROM subjects WHERE user_id = ? AND name = ?', (user_id, subject)).fetchone()
            if not existing:
                conn.execute('INSERT INTO subjects (user_id, name) VALUES (?, ?)', (user_id, subject))
        conn.execute('UPDATE tasks SET title=?, subject=?, priority=?, due_date=?, description=?, reminder_time=?, reminder_sound=? WHERE id=? AND user_id=?', (title, subject, priority, due_date, description, reminder_time if reminder_time else None, reminder_sound if reminder_sound else None, task_id, user_id))
        conn.commit()
        conn.close()
        flash('Task updated successfully!', 'success')
        return redirect(url_for('tasks'))
    subjects = conn.execute('SELECT * FROM subjects WHERE user_id = ?', (user_id,)).fetchall()
    sounds = conn.execute('SELECT * FROM reminder_sounds WHERE user_id = ?', (user_id,)).fetchall()
    conn.close()
    return render_template('edit_task.html', task=task, subjects=subjects, sounds=sounds)

@app.route('/calendar')
def calendar_view():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    user_id = session['user_id']
    year = request.args.get('year', datetime.now().year, type=int)
    month = request.args.get('month', datetime.now().month, type=int)
    first_weekday = calendar.monthrange(year, month)[0]
    days_in_month = calendar.monthrange(year, month)[1]
    conn = get_db()
    tasks_list = conn.execute("SELECT * FROM tasks WHERE user_id = ? AND strftime('%Y-%m', due_date) = ? ORDER BY due_date ASC", (user_id, f'{year}-{month:02d}')).fetchall()
    conn.close()
    return render_template('calendar.html', tasks=tasks_list, year=year, month=month, days_in_month=days_in_month, first_weekday=first_weekday, current_date=datetime.now())

@app.route('/statistics')
def statistics():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    user_id = session['user_id']
    conn = get_db()
    study_data = conn.execute("SELECT date, SUM(duration) as total FROM study_sessions WHERE user_id = ? AND date >= date('now', '-7 days') GROUP BY date ORDER BY date", (user_id,)).fetchall()
    task_stats = conn.execute('SELECT status, COUNT(*) as count FROM tasks WHERE user_id = ? GROUP BY status', (user_id,)).fetchall()
    subject_stats = conn.execute('SELECT subject, COUNT(*) as count FROM tasks WHERE user_id = ? GROUP BY subject', (user_id,)).fetchall()
    conn.close()

    # Build study hours labels and values (same logic as dashboard)
    study_map = {row['date']: row['total'] for row in study_data}
    study_labels = []
    study_values = []
    for i in range(6, -1, -1):
        day = datetime.now() - timedelta(days=i)
        study_labels.append(day.strftime('%a'))
        key = day.strftime('%Y-%m-%d')
        total = study_map.get(key, 0)
        study_values.append(round(total / 60, 1) if total else 0)

    # Build task status map
    task_status_map = {'completed': 0, 'in_progress': 0, 'pending': 0}
    total_tasks = 0
    for row in task_stats:
        if row['status'] in task_status_map:
            task_status_map[row['status']] = row['count']
        total_tasks += row['count']

    # Build subject chart data
    subject_names = []
    subject_counts = []
    subject_colors = []
    color_palette = ['#a855f7', '#3b82f6', '#10b981', '#f59e0b', '#ef4444', '#06b6d4', '#8b5cf6', '#f97316']
    for idx, row in enumerate(subject_stats):
        subject_names.append(row['subject'])
        subject_counts.append(row['count'])
        subject_colors.append(color_palette[idx % len(color_palette)])

    return render_template('statistics.html',
        study_labels=study_labels,
        study_values=study_values,
        task_status=task_status_map,
        total_tasks=total_tasks,
        subject_stats=subject_stats,
        subject_names=subject_names,
        subject_counts=subject_counts,
        subject_colors=subject_colors
    )
@app.route('/notes')
def notes():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    user_id = session['user_id']
    search = request.args.get('q', '').strip()
    conn = get_db()
    if search:
        notes_list = conn.execute('SELECT * FROM notes WHERE user_id = ? AND (title LIKE ? OR content LIKE ?) ORDER BY updated_at DESC', (user_id, f'%{search}%', f'%{search}%')).fetchall()
    else:
        notes_list = conn.execute('SELECT * FROM notes WHERE user_id = ? ORDER BY updated_at DESC', (user_id,)).fetchall()
    conn.close()
    return render_template('notes.html', notes=notes_list, search=search)

@app.route('/notes/new', methods=['GET', 'POST'])
def new_note():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    if request.method == 'POST':
        user_id = session['user_id']
        title = request.form.get('title', '').strip()
        content = request.form.get('content', '').strip()
        if not title:
            return render_template('new_note.html', error='Title is required', title=title, content=content)
        conn = get_db()
        conn.execute('INSERT INTO notes (user_id, title, content) VALUES (?, ?, ?)', (user_id, title, content))
        conn.commit()
        conn.close()
        flash('Note created successfully!', 'success')
        return redirect(url_for('notes'))
    return render_template('new_note.html', title='', content='', error=None)

@app.route('/notes/<int:note_id>/edit', methods=['GET', 'POST'])
def edit_note(note_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    user_id = session['user_id']
    conn = get_db()
    note = conn.execute('SELECT * FROM notes WHERE id = ? AND user_id = ?', (note_id, user_id)).fetchone()
    if not note:
        conn.close()
        flash('Note not found.', 'error')
        return redirect(url_for('notes'))
    if request.method == 'POST':
        title = request.form.get('title', '').strip()
        content = request.form.get('content', '').strip()
        if not title:
            conn.close()
            return render_template('edit_note.html', note=note, error='Title is required')
        conn.execute('UPDATE notes SET title = ?, content = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ? AND user_id = ?', (title, content, note_id, user_id))
        conn.commit()
        conn.close()
        flash('Note updated successfully!', 'success')
        return redirect(url_for('notes'))
    conn.close()
    return render_template('edit_note.html', note=note, error=None)

@app.route('/notes/<int:note_id>/delete', methods=['POST'])
def delete_note(note_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    user_id = session['user_id']
    conn = get_db()
    conn.execute('DELETE FROM notes WHERE id = ? AND user_id = ?', (note_id, user_id))
    conn.commit()
    conn.close()
    flash('Note deleted.', 'info')
    return redirect(url_for('notes'))

@app.route('/settings', methods=['GET', 'POST'])
def settings():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    user_id = session['user_id']
    conn = get_db()
    if request.method == 'POST':
        action = request.form.get('action')
        if action == 'add_subject':
            subject_name = request.form.get('subject_name', '').strip()
            subject_color = request.form.get('subject_color', '#7C3AED')
            if subject_name:
                existing = conn.execute('SELECT id FROM subjects WHERE user_id = ? AND name = ?', (user_id, subject_name)).fetchone()
                if not existing:
                    conn.execute('INSERT INTO subjects (user_id, name, color) VALUES (?, ?, ?)', (user_id, subject_name, subject_color))
                    conn.commit()
                    flash('Subject added!', 'success')
                else:
                    flash('Subject already exists.', 'error')
            else:
                flash('Subject name is required.', 'error')
        elif action == 'profile':
            name = request.form.get('name', '').strip()
            email = request.form.get('email', '').strip().lower()
            if not name or not email:
                user = conn.execute('SELECT * FROM users WHERE id = ?', (user_id,)).fetchone()
                subjects = conn.execute('SELECT * FROM subjects WHERE user_id = ?', (user_id,)).fetchall()
                sounds = conn.execute('SELECT * FROM reminder_sounds WHERE user_id = ?', (user_id,)).fetchall()
                conn.close()
                return render_template('settings.html', user=user, subjects=subjects, sounds=sounds, message='Name and email are required', message_type='error')
            existing = conn.execute('SELECT * FROM users WHERE email = ? AND id != ?', (email, user_id)).fetchone()
            if existing:
                user = conn.execute('SELECT * FROM users WHERE id = ?', (user_id,)).fetchone()
                subjects = conn.execute('SELECT * FROM subjects WHERE user_id = ?', (user_id,)).fetchall()
                sounds = conn.execute('SELECT * FROM reminder_sounds WHERE user_id = ?', (user_id,)).fetchall()
                conn.close()
                return render_template('settings.html', user=user, subjects=subjects, sounds=sounds, message='That email is already in use', message_type='error')
            conn.execute('UPDATE users SET name = ?, email = ? WHERE id = ?', (name, email, user_id))
            conn.commit()
            session['user_name'] = name
            flash('Profile updated successfully!', 'success')
        elif action == 'password':
            current_password = request.form.get('current_password', '')
            new_password = request.form.get('new_password', '')
            confirm_password = request.form.get('confirm_password', '')
            user = conn.execute('SELECT * FROM users WHERE id = ?', (user_id,)).fetchone()
            valid = check_password_hash(user['password'], current_password) if is_hashed(user['password']) else (user['password'] == current_password)
            if not valid:
                subjects = conn.execute('SELECT * FROM subjects WHERE user_id = ?', (user_id,)).fetchall()
                sounds = conn.execute('SELECT * FROM reminder_sounds WHERE user_id = ?', (user_id,)).fetchall()
                conn.close()
                return render_template('settings.html', user=user, subjects=subjects, sounds=sounds, message='Current password is incorrect', message_type='error')
            if new_password != confirm_password:
                subjects = conn.execute('SELECT * FROM subjects WHERE user_id = ?', (user_id,)).fetchall()
                sounds = conn.execute('SELECT * FROM reminder_sounds WHERE user_id = ?', (user_id,)).fetchall()
                conn.close()
                return render_template('settings.html', user=user, subjects=subjects, sounds=sounds, message='New passwords do not match', message_type='error')
            if len(new_password) < 6:
                subjects = conn.execute('SELECT * FROM subjects WHERE user_id = ?', (user_id,)).fetchall()
                sounds = conn.execute('SELECT * FROM reminder_sounds WHERE user_id = ?', (user_id,)).fetchall()
                conn.close()
                return render_template('settings.html', user=user, subjects=subjects, sounds=sounds, message='Password must be at least 6 characters', message_type='error')
            hashed = generate_password_hash(new_password)
            conn.execute('UPDATE users SET password = ? WHERE id = ?', (hashed, user_id))
            conn.commit()
            flash('Password changed successfully!', 'success')
        elif action == 'delete':
            confirm_email = request.form.get('confirm_email', '').strip().lower()
            user = conn.execute('SELECT * FROM users WHERE id = ?', (user_id,)).fetchone()
            if confirm_email != user['email']:
                subjects = conn.execute('SELECT * FROM subjects WHERE user_id = ?', (user_id,)).fetchall()
                sounds = conn.execute('SELECT * FROM reminder_sounds WHERE user_id = ?', (user_id,)).fetchall()
                conn.close()
                return render_template('settings.html', user=user, subjects=subjects, sounds=sounds, message='Email confirmation does not match', message_type='error')
            conn.execute('DELETE FROM tasks WHERE user_id = ?', (user_id,))
            conn.execute('DELETE FROM study_sessions WHERE user_id = ?', (user_id,))
            conn.execute('DELETE FROM subjects WHERE user_id = ?', (user_id,))
            conn.execute('DELETE FROM notes WHERE user_id = ?', (user_id,))
            conn.execute('DELETE FROM users WHERE id = ?', (user_id,))
            conn.commit()
            conn.close()
            session.clear()
            flash('Your account has been deleted.', 'info')
            return redirect(url_for('index'))
    user = conn.execute('SELECT * FROM users WHERE id = ?', (user_id,)).fetchone()
    subjects = conn.execute('SELECT * FROM subjects WHERE user_id = ?', (user_id,)).fetchall()
    sounds = conn.execute('SELECT * FROM reminder_sounds WHERE user_id = ?', (user_id,)).fetchall()
    conn.close()
    return render_template('settings.html', user=user, subjects=subjects, sounds=sounds, message=None, message_type=None)

# ===== API Routes =====

@app.route('/api/tasks/<int:task_id>', methods=['PUT', 'DELETE'])
@csrf.exempt
def task_action(task_id):
    if 'user_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 401
    conn = get_db()
    if request.method == 'PUT':
        data = request.get_json()
        status = data.get('status', 'completed')
        conn.execute('UPDATE tasks SET status = ? WHERE id = ? AND user_id = ?', (status, task_id, session['user_id']))
        conn.commit()
        conn.close()
        return jsonify({'success': True})
    elif request.method == 'DELETE':
        conn.execute('DELETE FROM tasks WHERE id = ? AND user_id = ?', (task_id, session['user_id']))
        conn.commit()
        conn.close()
        return jsonify({'success': True})

@app.route('/api/study-sessions', methods=['POST'])
@csrf.exempt
def log_study_session():
    if 'user_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 401
    data = request.get_json()
    subject = data.get('subject', '').strip()
    duration = data.get('duration', 0)
    if not subject or not duration or duration <= 0:
        return jsonify({'error': 'Subject and a positive duration are required'}), 400
    conn = get_db()
    conn.execute('INSERT INTO study_sessions (user_id, subject, duration, date) VALUES (?, ?, ?, ?)', (session['user_id'], subject, int(duration), datetime.now().strftime('%Y-%m-%d')))
    conn.commit()
    conn.close()
    return jsonify({'success': True})

@app.route('/api/subjects', methods=['POST'])
@csrf.exempt
def add_subject():
    if 'user_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 401
    data = request.get_json()
    name = data.get('name')
    color = data.get('color', '#7C3AED')
    conn = get_db()
    cursor = conn.execute('INSERT INTO subjects (user_id, name, color) VALUES (?, ?, ?)', (session['user_id'], name, color))
    subject_id = conn.lastrowid(cursor)
    conn.commit()
    conn.close()
    return jsonify({'id': subject_id, 'name': name, 'color': color})

@app.route('/api/check-reminders', methods=['POST'])
@csrf.exempt
def check_reminders():
    if 'user_id' not in session:
        return jsonify({'success': False, 'error': 'Unauthorized'}), 401
    user_id = session['user_id']
    now = datetime.now().strftime('%Y-%m-%d %H:%M')
    conn = get_db()
    due_tasks = conn.execute("SELECT * FROM tasks WHERE user_id = ? AND reminder_time IS NOT NULL AND reminder_time != '' AND reminder_notified = 0 AND datetime(reminder_time) <= datetime(?) AND datetime(reminder_time) >= datetime(?, '-5 minutes') AND status != 'completed'", (user_id, now, now)).fetchall()
    for task in due_tasks:
        conn.execute('UPDATE tasks SET reminder_notified = 1 WHERE id = ?', (task['id'],))
    conn.commit()
    conn.close()
    return jsonify({'success': True, 'due': [dict(t) for t in due_tasks]})

@app.route('/api/sounds/upload', methods=['POST'])
@csrf.exempt
def upload_sound():
    if 'user_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 401
    if os.environ.get('VERCEL') == '1':
        return jsonify({'error': 'File uploads are not supported on Vercel. Files are lost on each deployment.'}), 400
    if 'sound' not in request.files:
        return jsonify({'error': 'No file uploaded'}), 400
    file = request.files['sound']
    name = request.form.get('name', file.filename)
    if file.filename == '' or not allowed_file(file.filename):
        return jsonify({'error': 'Invalid file type. Allowed: mp3, wav, ogg, m4a, aac'}), 400
    ext = file.filename.rsplit('.', 1)[1].lower()
    unique_name = f'{uuid.uuid4().hex}.{ext}'
    file_path = os.path.join(UPLOAD_FOLDER, unique_name)
    file.save(file_path)
    rel_path = f'uploads/sounds/{unique_name}'
    conn = get_db()
    cursor = conn.execute('INSERT INTO reminder_sounds (user_id, name, file_path) VALUES (?, ?, ?)', (session['user_id'], name, rel_path))
    conn.commit()
    sound_id = conn.lastrowid(cursor)
    conn.close()
    return jsonify({'id': sound_id, 'name': name, 'file_path': rel_path})

@app.route('/api/sounds', methods=['GET'])
def get_sounds():
    if 'user_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 401
    conn = get_db()
    sounds = conn.execute('SELECT * FROM reminder_sounds WHERE user_id = ?', (session['user_id'],)).fetchall()
    conn.close()
    return jsonify([dict(s) for s in sounds])

@app.route('/api/sounds/<int:sound_id>/delete', methods=['POST'])
@csrf.exempt
def delete_sound(sound_id):
    if 'user_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 401
    conn = get_db()
    sound = conn.execute('SELECT * FROM reminder_sounds WHERE id = ? AND user_id = ?', (sound_id, session['user_id'])).fetchone()
    if not sound:
        conn.close()
        return jsonify({'error': 'Not found'}), 404
    file_path = os.path.join('static', sound['file_path'])
    if os.path.exists(file_path):
        os.remove(file_path)
    conn.execute('DELETE FROM reminder_sounds WHERE id = ?', (sound_id,))
    conn.commit()
    conn.close()
    return jsonify({'success': True})

@app.route('/api/subjects/<int:subject_id>/delete', methods=['POST'])
@csrf.exempt
def delete_subject(subject_id):
    if 'user_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 401
    conn = get_db()
    conn.execute('DELETE FROM subjects WHERE id = ? AND user_id = ?', (subject_id, session['user_id']))
    conn.commit()
    conn.close()
    return jsonify({'success': True})

if __name__ == '__main__':
    debug_mode = os.environ.get('FLASK_DEBUG', '1') == '1'
    app.run(debug=debug_mode, host='0.0.0.0', port=5000)
from flask import Flask, render_template, request, redirect, url_for, session, jsonify, send_from_directory, g
from datetime import datetime, timedelta
import os
import uuid
import secrets
import functools
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash
from flask_wtf.csrf import CSRFProtect
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

# ===== Database Backend Selection =====
# In production (Vercel) we use PostgreSQL via DATABASE_URL.
# In local development we fall back to SQLite.
DATABASE_URL = os.environ.get('DATABASE_URL', '')

if DATABASE_URL:
    import psycopg2
    import psycopg2.extras
    DB_IS_POSTGRES = True     
else:
    import sqlite3
    DB_IS_POSTGRES = False

app = Flask(__name__)
# SECRET_KEY is REQUIRED in production. In development a random key is generated.
# Set the SECRET_KEY environment variable on your deployment platform.
if os.environ.get('SECRET_KEY'):  
    app.secret_key = os.environ['SECRET_KEY'] 
else: 
    current_is_production = os.environ.get('FLASK_ENV') == 'production' or os.environ.get('VERCEL') == '1'
    if current_is_production:
        raise RuntimeError("SECRET_KEY environment variable must be set in production.")
    app.secret_key = secrets.token_hex(32)

# ===== Security Configuration =====
# Ensure cookies are transmitted securely
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'   
app.config['SESSION_COOKIE_SECURE'] = os.environ.get('COOKIE_SECURE', '0') == '1' 
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # Limit uploads to 16MB

# CSRF protection for all POST forms
csrf = CSRFProtect(app)

# Rate limiting to prevent brute-force / abuse
limiter = Limiter(
    get_remote_address,
    app=app,
    default_limits=["200 per day", "60 per hour"],
    storage_uri="memory://",
)

# ===== Security Headers =====
@app.after_request
def set_security_headers(response):
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'SAMEORIGIN'
    response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
    response.headers['X-XSS-Protection'] = '1; mode=block'
    response.headers['Permissions-Policy'] = 'geolocation=(), microphone=(), camera=()'
    # CSP - allow inline styles/scripts used by this app (Chart.js, Font Awesome)
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

# ===== Database wrapper: transparently supports SQLite (local) and PostgreSQL (prod) =====
class DB:
    """Unified connection wrapper so the rest of the app uses the same API."""
    def __init__(self, conn):
        self.conn = conn
        global DB_IS_POSTGRES
        self.is_postgres = DB_IS_POSTGRES

    def execute(self, sql, params=None):
        if self.is_postgres:
            # Translate SQLite-specific functions to PostgreSQL equivalents
            # (do this BEFORE converting ? -> %s so patterns match)
            sql = sql.replace("strftime('%Y-%m', due_date)", "LEFT(due_date, 7)")
            sql = sql.replace("date('now', '-7 days')", "(CURRENT_DATE - INTERVAL '7 days')")
            sql = sql.replace("datetime(reminder_time) <= datetime(?)",
                              "reminder_time::timestamp <= %s::timestamp")
            sql = sql.replace("datetime(reminder_time) >= datetime(?, '-5 minutes')",
                              "reminder_time::timestamp >= %s::timestamp - INTERVAL '5 minutes'")
            # For INSERT statements, append RETURNING id so we can get the new row id
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

    def cursor(self):
        return self.conn.cursor()

    def lastrowid(self, cursor):
        """Return the last inserted row id (works for both SQLite and PostgreSQL)."""
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
        # ---- PostgreSQL table definitions ----
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id SERIAL PRIMARY KEY,
                email VARCHAR(255) UNIQUE NOT NULL,
                password TEXT NOT NULL,
                name VARCHAR(255) DEFAULT 'Student',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        cursor.execute("""
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
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS study_sessions (
                id SERIAL PRIMARY KEY,
                user_id INTEGER NOT NULL REFERENCES users (id),
                subject TEXT NOT NULL,
                duration INTEGER NOT NULL,
                date TEXT NOT NULL
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS subjects (
                id SERIAL PRIMARY KEY,
                user_id INTEGER NOT NULL REFERENCES users (id),
                name TEXT NOT NULL,
                color TEXT DEFAULT '#7C3AED'
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS notes (
                id SERIAL PRIMARY KEY,
                user_id INTEGER NOT NULL REFERENCES users (id),
                title TEXT NOT NULL,
                content TEXT DEFAULT '',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS reminder_sounds (
                id SERIAL PRIMARY KEY,
                user_id INTEGER NOT NULL REFERENCES users (id),
                name TEXT NOT NULL,
                file_path TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
    else:
        # ---- SQLite table definitions ----
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email TEXT UNIQUE NOT NULL,
                password TEXT NOT NULL,
                name TEXT DEFAULT 'Student',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        cursor.execute("""
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
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS study_sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                subject TEXT NOT NULL,
                duration INTEGER NOT NULL,
                date TEXT NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users (id)
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS subjects (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                name TEXT NOT NULL,
                color TEXT DEFAULT '#7C3AED',
                FOREIGN KEY (user_id) REFERENCES users (id)
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS notes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                title TEXT NOT NULL,
                content TEXT DEFAULT '',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users (id)
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS reminder_sounds (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                name TEXT NOT NULL,
                file_path TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users (id)
            )
        """)

        # Migrate existing tasks table if reminder columns missing
        try:
            cursor.execute('SELECT reminder_time FROM tasks LIMIT 1')
        except sqlite3.OperationalError:
            cursor.execute("ALTER TABLE tasks ADD COLUMN reminder_time TEXT")
            cursor.execute("ALTER TABLE tasks ADD COLUMN reminder_sound TEXT")
            cursor.execute("ALTER TABLE tasks ADD COLUMN reminder_notified INTEGER DEFAULT 0")

    conn.commit()
    conn.close()

# Initialize database on startup
init_db()

# Password helpers
def is_hashed(password):
    """Check if a stored password is already hashed (werkzeug) vs plaintext."""
    return password.startswith(('scrypt:', 'pbkdf2:', 'sha256:'))

def migrate_plaintext_passwords():
    """Upgrade any legacy plaintext passwords to secure hashes (safe on every startup)."""
    conn = get_db()
    users = conn.execute('SELECT id, password FROM users').fetchall()
    for u in users:
        if not is_hashed(u['password']):
            hashed = generate_password_hash(u['password'])
            conn.execute('UPDATE users SET password=? WHERE id=?', (hashed, u['id']))
    conn.commit()
    conn.close()

# Upgrade legacy plaintext passwords to hashes
migrate_plaintext_passwords()

@app.route('/')
def index():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    return redirect(url_for('dashboard'))

@app.route('/login', methods=['GET', 'POST'])
@limiter.limit("10 per minute")
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
            if is_hashed(stored):
                valid = check_password_hash(stored, password)
            else:
                valid = (stored == password)

            if valid:
                # Regenerate session ID to prevent session fixation
                session.clear()
                session['user_id'] = user['id']
                session['user_name'] = user['name']
                return redirect(url_for('dashboard'))
            else:
                return render_template('login.html', error='Invalid email or password')
        else:
            return render_template('login.html', error='Invalid email or password')

    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        email = request.form['email'].strip().lower()
        password = request.form['password']
        name = request.form.get('name', 'Student')

        conn = get_db()
        try:
            hashed = generate_password_hash(password)
            conn.execute('INSERT INTO users (email, password, name) VALUES (?, ?, ?)',
                        (email, hashed, name))
            conn.commit()
            conn.close()
            return redirect(url_for('login'))
        except Exception:
            conn.close()
            return render_template('login.html', error='Email already exists')

    return redirect(url_for('login'))

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    user_id = session['user_id']
    conn = get_db()

    today = datetime.now().strftime('%Y-%m-%d')
    tasks_today = conn.execute('SELECT COUNT(*) as count FROM tasks WHERE user_id = ? AND due_date = ?',
                            (user_id, today)).fetchone()['count']

    tasks_completed = conn.execute('SELECT COUNT(*) as count FROM tasks WHERE user_id = ? AND status = ?',
                                (user_id, 'completed')).fetchone()['count']

    total_tasks = conn.execute('SELECT COUNT(*) as count FROM tasks WHERE user_id = ?',
                            (user_id,)).fetchone()['count']

    study_hours = conn.execute('SELECT SUM(duration) as total FROM study_sessions WHERE user_id = ?',
                            (user_id,)).fetchone()['total'] or 0
    study_hours = round(study_hours / 60, 1)

    # Count distinct subjects from both the subjects table AND the tasks table,
    # so the "Subjects" stat reflects what the user actually uses.
    subjects_count = conn.execute('SELECT COUNT(*) as count FROM subjects WHERE user_id = ?',
                                (user_id,)).fetchone()['count']
    task_subjects_count = conn.execute("""
        SELECT COUNT(DISTINCT subject) as count FROM tasks 
        WHERE user_id = ? AND subject IS NOT NULL AND subject != ''
    """, (user_id,)).fetchone()['count']
    subjects_count = subjects_count + task_subjects_count

    upcoming_tasks = conn.execute("""
        SELECT * FROM tasks 
        WHERE user_id = ? AND status != 'completed' 
        ORDER BY due_date ASC LIMIT 5
    """, (user_id,)).fetchall()

    # Overdue tasks (not completed and past due date)
    overdue_count = conn.execute("""
        SELECT COUNT(*) as count FROM tasks 
        WHERE user_id = ? AND status != 'completed' AND due_date < ?
    """, (user_id, today)).fetchone()['count']

    subjects = conn.execute('SELECT * FROM subjects WHERE user_id = ?', (user_id,)).fetchall()

    # Task status breakdown for the donut chart
    task_status = conn.execute("""
        SELECT status, COUNT(*) as count FROM tasks WHERE user_id = ? GROUP BY status
    """, (user_id,)).fetchall()
    status_map = {'pending': 0, 'in_progress': 0, 'completed': 0}
    for row in task_status:
        if row['status'] in status_map:
            status_map[row['status']] = row['count']

    # Weekly study data for the focus chart (last 7 days)
    focus_data = conn.execute("""
        SELECT date, SUM(duration) as total FROM study_sessions 
        WHERE user_id = ? AND date >= date('now', '-7 days')
        GROUP BY date ORDER BY date
    """, (user_id,)).fetchall()
    focus_map = {row['date']: row['total'] for row in focus_data}

    # Daily average focus time (from study sessions)
    daily_avg = None
    if focus_data:
        total_minutes = sum(row['total'] for row in focus_data)
        daily_avg = round(total_minutes / 7 / 60, 1)

    # Build last 7 days labels + values for the focus line chart
    focus_labels = []
    focus_values = []
    for i in range(6, -1, -1):
        day = datetime.now() - timedelta(days=i)
        focus_labels.append(day.strftime('%a'))
        key = day.strftime('%Y-%m-%d')
        total = focus_map.get(key, 0)
        focus_values.append(round(total / 60, 1) if total else 0)

    conn.close()

    return render_template('dashboard.html', 
    user_name=session.get('user_name', 'Student'),
    tasks_today=tasks_today,
    tasks_completed=tasks_completed,
    total_tasks=total_tasks,
    overdue_count=overdue_count,
    study_hours=study_hours,
    subjects_count=subjects_count,
    upcoming_tasks=upcoming_tasks,
    subjects=subjects,
    task_status=status_map,
    focus_data=focus_map,
    daily_avg=daily_avg,
    focus_labels=focus_labels,
    focus_values=focus_values)

@app.route('/tasks')
def tasks():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    user_id = session['user_id']
    filter_status = request.args.get('status', 'all')

    conn = get_db()
    if filter_status == 'all':
        tasks_list = conn.execute('SELECT * FROM tasks WHERE user_id = ? ORDER BY due_date ASC',
        (user_id,)).fetchall()
    else:
        tasks_list = conn.execute('SELECT * FROM tasks WHERE user_id = ? AND status = ? ORDER BY due_date ASC',
        (user_id, filter_status)).fetchall()

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

        # If user typed a custom subject, save it to subjects table
        custom_subject = request.form.get('custom_subject', '').strip()
        if custom_subject and not subject:
            subject = custom_subject
            conn_ck = get_db()
            existing = conn_ck.execute('SELECT id FROM subjects WHERE user_id = ? AND name = ?',
                  (user_id, subject)).fetchone()
            if not existing:
                conn_ck.execute('INSERT INTO subjects (user_id, name) VALUES (?, ?)',
                        (user_id, subject))
            conn_ck.commit()
            conn_ck.close()

        conn = get_db()
        conn.execute("""
            INSERT INTO tasks (user_id, title, subject, priority, due_date, description, reminder_time, reminder_sound)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (user_id, title, subject, priority, due_date, description,
              reminder_time if reminder_time else None,
              reminder_sound if reminder_sound else None))
        conn.commit()
        conn.close()

        return redirect(url_for('tasks'))

    conn = get_db()
    subjects = conn.execute('SELECT * FROM subjects WHERE user_id = ?',
    (session['user_id'],)).fetchall()
    sounds = conn.execute('SELECT * FROM reminder_sounds WHERE user_id = ?',
                         (session['user_id'],)).fetchall()
    conn.close()

    return render_template('add_task.html', subjects=subjects, sounds=sounds)

@app.route('/edit_task/<int:task_id>', methods=['GET', 'POST'])
def edit_task(task_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))

    user_id = session['user_id']
    conn = get_db()
    task = conn.execute('SELECT * FROM tasks WHERE id = ? AND user_id = ?',
                        (task_id, user_id)).fetchone()
    if not task:
        conn.close()
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
            existing = conn.execute('SELECT id FROM subjects WHERE user_id = ? AND name = ?',
                                   (user_id, subject)).fetchone()
            if not existing:
                conn.execute('INSERT INTO subjects (user_id, name) VALUES (?, ?)',
                           (user_id, subject))

        conn.execute("""
            UPDATE tasks SET title=?, subject=?, priority=?, due_date=?, description=?,
            reminder_time=?, reminder_sound=?
            WHERE id=? AND user_id=?
        """, (title, subject, priority, due_date, description,
              reminder_time if reminder_time else None,
              reminder_sound if reminder_sound else None,
              task_id, user_id))
        conn.commit()
        conn.close()
        return redirect(url_for('tasks'))

    subjects = conn.execute('SELECT * FROM subjects WHERE user_id = ?', (user_id,)).fetchall()
    sounds = conn.execute('SELECT * FROM reminder_sounds WHERE user_id = ?', (user_id,)).fetchall()
    conn.close()
    return render_template('edit_task.html', task=task, subjects=subjects, sounds=sounds)

@app.route('/calendar')
def calendar():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    user_id = session['user_id']
    year = request.args.get('year', datetime.now().year, type=int)
    month = request.args.get('month', datetime.now().month, type=int)

    conn = get_db()
    tasks_list = conn.execute("""
        SELECT * FROM tasks WHERE user_id = ? 
        AND strftime('%Y-%m', due_date) = ?
        ORDER BY due_date ASC
    """, (user_id, f'{year}-{month:02d}')).fetchall()
    conn.close()

    return render_template('calendar.html', 
                         tasks=tasks_list, 
                         year=year, 
                         month=month,
                         current_date=datetime.now())

@app.route('/statistics')
def statistics():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    user_id = session['user_id']
    conn = get_db()

    # Get weekly study hours
    study_data = conn.execute("""
        SELECT date, SUM(duration) as total 
        FROM study_sessions 
        WHERE user_id = ? 
        AND date >= date('now', '-7 days')
        GROUP BY date
        ORDER BY date
    """, (user_id,)).fetchall()

    # Get task completion stats
    task_stats = conn.execute("""
        SELECT status, COUNT(*) as count 
        FROM tasks 
        WHERE user_id = ?
        GROUP BY status
    """, (user_id,)).fetchall()

    # Get subject distribution
    subject_stats = conn.execute("""
        SELECT subject, COUNT(*) as count 
        FROM tasks 
        WHERE user_id = ?
        GROUP BY subject
    """, (user_id,)).fetchall()

    conn.close()

    return render_template('statistics.html',
                         study_data=study_data,
                         task_stats=task_stats,
                         subject_stats=subject_stats)

@app.route('/notes')
def notes():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    user_id = session['user_id']
    search = request.args.get('q', '').strip()

    conn = get_db()
    if search:
        notes_list = conn.execute("""
            SELECT * FROM notes 
            WHERE user_id = ? AND (title LIKE ? OR content LIKE ?)
            ORDER BY updated_at DESC
        """, (user_id, f'%{search}%', f'%{search}%')).fetchall()
    else:
        notes_list = conn.execute("""
            SELECT * FROM notes 
            WHERE user_id = ? 
            ORDER BY updated_at DESC
        """, (user_id,)).fetchall()
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
        conn.execute("""
            INSERT INTO notes (user_id, title, content) VALUES (?, ?, ?)
        """, (user_id, title, content))
        conn.commit()
        conn.close()

        return redirect(url_for('notes'))

    return render_template('new_note.html', title='', content='', error=None)

@app.route('/notes/<int:note_id>/edit', methods=['GET', 'POST'])
def edit_note(note_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))

    user_id = session['user_id']
    conn = get_db()
    note = conn.execute('SELECT * FROM notes WHERE id = ? AND user_id = ?',
                        (note_id, user_id)).fetchone()
    conn.close()

    if not note:
        return redirect(url_for('notes'))

    if request.method == 'POST':
        title = request.form.get('title', '').strip()
        content = request.form.get('content', '').strip()

        if not title:
            return render_template('edit_note.html', note=note, error='Title is required')

        conn = get_db()
        conn.execute("""
            UPDATE notes SET title = ?, content = ?, updated_at = CURRENT_TIMESTAMP 
            WHERE id = ? AND user_id = ?
        """, (title, content, note_id, user_id))
        conn.commit()
        conn.close()

        return redirect(url_for('notes'))

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

    return redirect(url_for('notes'))

@app.route('/settings', methods=['GET', 'POST'])
def settings():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    user_id = session['user_id']
    conn = get_db()

    if request.method == 'POST':
        action = request.form.get('action')

        # --- Add Subject ---
        if action == 'add_subject':
            subject_name = request.form.get('subject_name', '').strip()
            subject_color = request.form.get('subject_color', '#7C3AED')

            if subject_name:
                existing = conn.execute('SELECT id FROM subjects WHERE user_id = ? AND name = ?',
                                        (user_id, subject_name)).fetchone()
                if not existing:
                    conn.execute('INSERT INTO subjects (user_id, name, color) VALUES (?, ?, ?)',
                                 (user_id, subject_name, subject_color))
                    conn.commit()

            subjects = conn.execute('SELECT * FROM subjects WHERE user_id = ?', (user_id,)).fetchall()
            sounds = conn.execute('SELECT * FROM reminder_sounds WHERE user_id = ?', (user_id,)).fetchall()
            user = conn.execute('SELECT * FROM users WHERE id = ?', (user_id,)).fetchone()
            conn.close()
            return render_template('settings.html', user=user, subjects=subjects, sounds=sounds, message='Subject added successfully!', message_type='success')

        # --- Update Profile ---
        if action == 'profile':
            name = request.form.get('name', '').strip()
            email = request.form.get('email', '').strip().lower()

            if not name or not email:
                user = conn.execute('SELECT * FROM users WHERE id = ?', (user_id,)).fetchone()
                subjects = conn.execute('SELECT * FROM subjects WHERE user_id = ?', (user_id,)).fetchall()
                sounds = conn.execute('SELECT * FROM reminder_sounds WHERE user_id = ?', (user_id,)).fetchall()
                conn.close()
                return render_template('settings.html', user=user, subjects=subjects, sounds=sounds, message='Name and email are required', message_type='error')

            existing = conn.execute('SELECT * FROM users WHERE email = ? AND id != ?',
                                    (email, user_id)).fetchone()
            if existing:
                user = conn.execute('SELECT * FROM users WHERE id = ?', (user_id,)).fetchone()
                subjects = conn.execute('SELECT * FROM subjects WHERE user_id = ?', (user_id,)).fetchall()
                sounds = conn.execute('SELECT * FROM reminder_sounds WHERE user_id = ?', (user_id,)).fetchall()
                conn.close()
                return render_template('settings.html', user=user, subjects=subjects, sounds=sounds, message='That email is already in use', message_type='error')

            conn.execute('UPDATE users SET name = ?, email = ? WHERE id = ?', (name, email, user_id))
            conn.commit()
            session['user_name'] = name
            user = conn.execute('SELECT * FROM users WHERE id = ?', (user_id,)).fetchone()
            subjects = conn.execute('SELECT * FROM subjects WHERE user_id = ?', (user_id,)).fetchall()
            sounds = conn.execute('SELECT * FROM reminder_sounds WHERE user_id = ?', (user_id,)).fetchall()
            conn.close()
            return render_template('settings.html', user=user, subjects=subjects, sounds=sounds, message='Profile updated successfully!', message_type='success')

        # --- Change Password ---
        elif action == 'password':
            current_password = request.form.get('current_password', '')
            new_password = request.form.get('new_password', '')
            confirm_password = request.form.get('confirm_password', '')

            user = conn.execute('SELECT * FROM users WHERE id = ?', (user_id,)).fetchone()

            if is_hashed(user['password']):
                valid = check_password_hash(user['password'], current_password)
            else:
                valid = (user['password'] == current_password)

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
            user = conn.execute('SELECT * FROM users WHERE id = ?', (user_id,)).fetchone()
            subjects = conn.execute('SELECT * FROM subjects WHERE user_id = ?', (user_id,)).fetchall()
            sounds = conn.execute('SELECT * FROM reminder_sounds WHERE user_id = ?', (user_id,)).fetchall()
            conn.close()
            return render_template('settings.html', user=user, subjects=subjects, sounds=sounds, message='Password changed successfully!', message_type='success')

        # --- Delete Account ---
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
            return redirect(url_for('login'))

    user = conn.execute('SELECT * FROM users WHERE id = ?', (user_id,)).fetchone()
    subjects = conn.execute('SELECT * FROM subjects WHERE user_id = ?', (user_id,)).fetchall()
    sounds = conn.execute('SELECT * FROM reminder_sounds WHERE user_id = ?', (user_id,)).fetchall()
    conn.close()
    return render_template('settings.html', user=user, subjects=subjects, sounds=sounds, message=None, message_type=None)

# API Routes for AJAX
@app.route('/api/tasks/<int:task_id>', methods=['PUT', 'DELETE'])
def task_action(task_id):
    if 'user_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 401

    conn = get_db()

    if request.method == 'PUT':
        data = request.get_json()
        status = data.get('status', 'completed')
        conn.execute('UPDATE tasks SET status = ? WHERE id = ? AND user_id = ?',
                      (status, task_id, session['user_id']))
        conn.commit()
        conn.close()
        return jsonify({'success': True})

    elif request.method == 'DELETE':
        conn.execute('DELETE FROM tasks WHERE id = ? AND user_id = ?',
                      (task_id, session['user_id']))
        conn.commit()
        conn.close()
        return jsonify({'success': True})

@app.route('/api/study-sessions', methods=['POST'])
def log_study_session():
    if 'user_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 401

    data = request.get_json()
    subject = data.get('subject', '').strip()
    duration = data.get('duration', 0)

    if not subject or not duration or duration <= 0:
        return jsonify({'error': 'Subject and a positive duration are required'}), 400

    conn = get_db()
    conn.execute('INSERT INTO study_sessions (user_id, subject, duration, date) VALUES (?, ?, ?, ?)',
                 (session['user_id'], subject, int(duration), datetime.now().strftime('%Y-%m-%d')))
    conn.commit()
    conn.close()

    return jsonify({'success': True})

@app.route('/api/subjects', methods=['POST'])
def add_subject():
    if 'user_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 401

    data = request.get_json()
    name = data.get('name')
    color = data.get('color', '#7C3AED')

    conn = get_db()
    cursor = conn.execute('INSERT INTO subjects (user_id, name, color) VALUES (?, ?, ?)',
                         (session['user_id'], name, color))
    subject_id = conn.lastrowid(cursor)
    conn.commit()
    conn.close()

    return jsonify({'id': subject_id, 'name': name, 'color': color})

@app.route('/api/check-reminders', methods=['POST'])
def check_reminders():
    if 'user_id' not in session:
        return jsonify({'success': False, 'error': 'Unauthorized'}), 401

    user_id = session['user_id']
    now = datetime.now().strftime('%Y-%m-%d %H:%M')

    conn = get_db()
    # Find tasks with reminders due within the last 5 minutes that haven't been notified
    due_tasks = conn.execute("""
        SELECT * FROM tasks 
        WHERE user_id = ? AND reminder_time IS NOT NULL AND reminder_time != ''
        AND reminder_notified = 0
        AND datetime(reminder_time) <= datetime(?) 
        AND datetime(reminder_time) >= datetime(?, '-5 minutes')
        AND status != 'completed'
    """, (user_id, now, now)).fetchall()

    # Mark them as notified
    for task in due_tasks:
        conn.execute('UPDATE tasks SET reminder_notified = 1 WHERE id = ?', (task['id'],))
    conn.commit()
    conn.close()

    return jsonify({'success': True, 'due': [dict(t) for t in due_tasks]})

# Upload / serve reminder sounds
@app.route('/api/sounds/upload', methods=['POST'])
def upload_sound():
    if 'user_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 401

    if 'sound' not in request.files:
        return jsonify({'error': 'No file uploaded'}), 400

    file = request.files['sound']
    name = request.form.get('name', file.filename)

    if file.filename == '' or not allowed_file(file.filename):
        return jsonify({'error': 'Invalid file type. Allowed: mp3, wav, ogg, m4a, aac'}), 400

    # Save file with unique name
    ext = file.filename.rsplit('.', 1)[1].lower()
    unique_name = f"{uuid.uuid4().hex}.{ext}"
    file_path = os.path.join(UPLOAD_FOLDER, unique_name)
    file.save(file_path)

# Relative path for serving
    rel_path = f"uploads/sounds/{unique_name}"

    conn = get_db()
    cursor = conn.execute('INSERT INTO reminder_sounds (user_id, name, file_path) VALUES (?, ?, ?)',
                         (session['user_id'], name, rel_path))
    conn.commit()
    sound_id = conn.lastrowid(cursor)
    conn.close()

    return jsonify({'id': sound_id, 'name': name, 'file_path': rel_path})

@app.route('/api/sounds', methods=['GET'])
def get_sounds():
    if 'user_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 401

    conn = get_db()
    sounds = conn.execute('SELECT * FROM reminder_sounds WHERE user_id = ?',
                         (session['user_id'],)).fetchall()
    conn.close()

    return jsonify([dict(s) for s in sounds])

@app.route('/api/sounds/<int:sound_id>/delete', methods=['POST'])
def delete_sound(sound_id):
    if 'user_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 401

    conn = get_db()
    sound = conn.execute('SELECT * FROM reminder_sounds WHERE id = ? AND user_id = ?',
                        (sound_id, session['user_id'])).fetchone()
    if not sound:
        conn.close()
        return jsonify({'error': 'Not found'}), 404

    # Delete file from disk
    file_path = os.path.join('static', sound['file_path'])
    if os.path.exists(file_path):
        os.remove(file_path)

    conn.execute('DELETE FROM reminder_sounds WHERE id = ?', (sound_id,))
    conn.commit()
    conn.close()

    return jsonify({'success': True})

@app.route('/api/subjects/<int:subject_id>/delete', methods=['POST'])
def delete_subject(subject_id):
    if 'user_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 401

    conn = get_db()
    conn.execute('DELETE FROM subjects WHERE id = ? AND user_id = ?',
                (subject_id, session['user_id']))
    conn.commit()
    conn.close()
    return jsonify({'success': True})

if __name__ == '__main__':
    debug_mode = os.environ.get('FLASK_DEBUG', '1') == '1'
    app.run(debug=debug_mode, host='0.0.0.0', port=5000)

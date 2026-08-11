# Study Planner

A modern, full-featured personal study management web application built with Python (Flask), SQLite/PostgreSQL, HTML, CSS, and JavaScript. It helps students and self-learners organize their academic life by tracking tasks, taking notes, setting reminders, and monitoring study progress — all from a single, mobile-friendly interface.

## Table of Contents

- [Overview](#overview)
- [Features](#features)
- [Tech Stack](#tech-stack)
- [Installation](#installation)
- [Running the Application](#running-the-application)
- [Creating a User Account](#creating-a-user-account)
- [Usage Guide](#usage-guide)
- [Project Structure](#project-structure)
- [Troubleshooting](#troubleshooting)
- [Deploying to Vercel](#deploying-to-vercel)
- [Security](#security)
- [Contributing](#contributing)
- [Future Enhancements](#future-enhancements)
- [License](#license)

---

## Overview

Study Planner is a personal productivity tool that consolidates task management, notes, calendaring, and analytics into a single web application. It is designed for students, self-learners, and professionals who want to bring structure to their daily activities.

The application provides:

- A smart task management system with priorities, due dates, and reminders
- A study calendar with monthly overview
- Statistical charts for tracking study habits and completion rates
- A personal notes system with search capability
- A customizable settings panel for profile, password, subjects, and reminder sounds

---

## Features

### Authentication and Security

- Email and password login
- New account registration
- Password change and account deletion (with confirmation)
- Passwords stored as secure hashes using Werkzeug
- Development auto-login route at `/auto-login`

### Dashboard

The primary landing page after login provides a summary of the user's academic activities:

- Tasks due today
- Tasks completed
- Total study hours logged
- Number of subjects tracked
- Upcoming tasks preview
- Progress charts visualizing study habits

### Task Management

Full CRUD operations for tasks:

- Task title, subject, priority (High/Medium/Low), due date, and description
- Optional reminder time and reminder sound
- Filter by status: All, Pending, In Progress, Completed
- Mark tasks complete with a single click
- Edit and delete tasks

### Notes

- Create, edit, and delete notes
- Keyword search across notes
- Automatic sorting by most recently updated

### Calendar

- Monthly calendar view
- Dot indicators on days with tasks
- Current day highlighted
- Month navigation for planning ahead

### Statistics

- Weekly study hours chart
- Task completion status breakdown
- Subject distribution analysis

### Settings

- Profile editing (name, email)
- Password change
- Subject management with custom colors
- Reminder sound upload (MP3, WAV, OGG, M4A, AAC)
- Account deletion with email confirmation

### Responsive Design

- Fully responsive layout for desktop, tablet, and mobile
- Collapsible sidebar on smaller screens
- Adaptive layouts and typography

---

## Tech Stack

| Technology | Purpose |
|---|---|
| Python 3.14 | Programming language |
| Flask 3.1 | Web framework |
| SQLite | Local development database |
| PostgreSQL | Production database (Vercel / Neon) |
| HTML5 | Page structure |
| CSS3 | Styling and layout |
| JavaScript | Frontend interactivity |
| Chart.js | Chart rendering |
| Font Awesome | Iconography |
| Werkzeug | Password hashing |
| Flask-WTF | CSRF protection |
| Flask-Limiter | Rate limiting |

---

## Installation

### Prerequisites

- Python 3.8 or later
- pip (Python package installer)
- A modern web browser

### Setup

1. Clone or download the repository and navigate to the project directory:

```bash
git clone https://github.com/yourusername/study-planner.git
cd study-planner
```

2. Create and activate a virtual environment (recommended):

**Windows**

```bash
python -m venv venv
venv\Scripts\activate
```

**macOS / Linux**

```bash
python3 -m venv venv
source venv/bin/activate
```

3. Install dependencies:

```bash
pip install -r requirements.txt
```

---

## Running the Application

### Option 1: One-Click Launcher

The `run.py` script starts the server and automatically opens the default browser:

```bash
python run.py
```

### Option 2: Standard Flask Server

```bash
python app.py
```

### Access

Once the server is running, open your browser at:

```
http://127.0.0.1:5000
```

The server binds to `0.0.0.0:5000`, so other devices on the same network can also access the app using your computer's IP address and port 5000.

> Note: Run only one of the commands above at a time. Starting a second server while one is active will result in a port conflict.

---

## Creating a User Account

All passwords are stored as secure hashes. Do not commit real email addresses or passwords to a public repository.

To create a user or reset a password locally, use the helper script:

```bash
python set_password.py your@email.com YourTemporaryPassword
```

Alternatively, register directly through the application's "Sign up" link on the login page.

---

## Usage Guide

### Getting Started

1. Start the application with `python run.py`.
2. Open `http://127.0.0.1:5000` in your browser.
3. Log in with your credentials, or click "Sign up" to create a new account.
4. You will be redirected to the Dashboard.

### Adding a Task

1. Click **Tasks** in the sidebar.
2. Click the floating **+** (Add) button.
3. Enter task details (title, subject, priority, due date, optional description and reminder).
4. Click **Save Task**.

### Completing a Task

On the Tasks page, click the green check button next to a task. Its status updates to "Completed".

### Taking Notes

1. Click **Notes** in the sidebar.
2. Select **New Note**.
3. Enter a title and content, then save.

### Setting a Reminder

1. When adding or editing a task, set a reminder time (date and time).
2. Choose a reminder sound, or upload your own in Settings.
3. Save the task. The application will notify you when the reminder time arrives.

### Managing Subjects

1. Navigate to **Settings -> My Subjects**.
2. Add a subject with a name and color.
3. Delete subjects no longer needed.

### Recommended Daily Workflow

1. Morning: Open the Dashboard and review tasks due today.
2. Review prioritized pending tasks.
3. Complete tasks as they are finished and track progress.
4. Take notes during study sessions.
5. Plan upcoming tasks and deadlines.
6. Evening: Review Statistics to monitor progress.

---

## Project Structure

```
study-planner/
├── app.py                    # Main Flask application (routes and logic)
├── api/
│   └── index.py              # Vercel serverless entry point
├── run.py                    # One-click launcher (server + browser)
├── set_password.py           # Password reset helper script
├── create_test_user.py       # Creates a test user (optional)
├── show_users.py             # Debug tool to list database users
├── reset_user_password.py    # Resets a user's password (with backup)
├── vercel.json               # Vercel deployment config
├── requirements.txt          # Python dependencies
├── study_planner.db          # SQLite database (local only)
├── README.md                 # Project documentation
├── LICENSE                   # MIT License
├── CONTRIBUTING.md           # Contribution guidelines
├── CODE_OF_CONDUCT.md        # Community code of conduct
├── static/
│   ├── css/
│   │   └── style.css         # Application styling
│   ├── js/
│   │   └── main.js           # Frontend interactivity
│   ├── images/               # Application images
│   └── uploads/
│       └── sounds/           # User-uploaded reminder sounds
└── templates/
    ├── base.html             # Base layout
    ├── login.html            # Login and registration
    ├── dashboard.html        # Dashboard
    ├── tasks.html            # Task list
    ├── add_task.html         # Create task
    ├── edit_task.html        # Edit task
    ├── calendar.html         # Calendar view
    ├── statistics.html       # Statistics and charts
    ├── notes.html            # Notes list
    ├── new_note.html         # Create note
    ├── edit_note.html        # Edit note
    └── settings.html         # Settings panel
```

---

## Troubleshooting

### "can't open file 'run'" error

This occurs when the command is entered as `python run app.py` instead of `python run.py`. Always include the `.py` extension.

### Application skips the login page

The application is skipping the login page because a session is already active. To log out, visit:

```
http://127.0.0.1:5000/logout
```

Then open the application root again to reach the login page.

### Port 5000 already in use

A port conflict occurs when another server instance is already running. Stop the existing server, or open `http://127.0.0.1:5000` directly in the browser to use the running instance.

### "Invalid email or password"

- Verify the email and password are correct (they are case-sensitive).
- Reset the password using the helper script:

```bash
python set_password.py your@email.com NewPassword123
```

### Database issues

A backup of the database is created automatically as `study_planner.db.bak` when running `reset_user_password.py`. Restore it if needed, or delete it to start fresh.

---

## Deploying to Vercel

The app is fully configured for serverless deployment on [Vercel](https://vercel.com) with PostgreSQL as the production database.

### Prerequisites

- A [Vercel](https://vercel.com) account
- A PostgreSQL database (e.g., [Neon](https://neon.tech), [Supabase](https://supabase.com), or [Railway](https://railway.app))

### Steps

1. **Push your code to GitHub** and import the repository in Vercel.

2. **Set environment variables** in Vercel's dashboard (Project → Settings → Environment Variables):
   - `SECRET_KEY` — a long random string (required). Generate one with:
     ```bash
     python -c "import secrets; print(secrets.token_hex(32))"
     ```
   - `DATABASE_URL` — your PostgreSQL connection string
   - `COOKIE_SECURE` — set to `1` in production

3. **Deploy.** Vercel automatically uses the existing `vercel.json` and `api/index.py` entry point. No additional build settings needed.

4. **Create your first user** by visiting `/register` on your deployed app.

> **Note:** The free SQLite database is for local development only. Vercel's serverless filesystem is ephemeral, so PostgreSQL is required for persistent data in production.

---

## Security

The application includes multiple layers of security hardening:

- **Password hashing** — All passwords are stored as secure hashes using Werkzeug's `generate_password_hash` (scrypt/pbkdf2). Legacy plaintext passwords are automatically migrated on startup.
- **CSRF protection** — All POST forms are protected via Flask-WTF.
- **Rate limiting** — Login attempts are limited to 10 per minute; global default limits apply (60/hour, 200/day).
- **Session security** — Cookies are `HttpOnly`, `SameSite=Lax`, and optionally `Secure`. Session IDs are regenerated on login to prevent session fixation.
- **Security headers** — `X-Content-Type-Options`, `X-Frame-Options`, `Referrer-Policy`, `X-XSS-Protection`, `Permissions-Policy`, and a Content-Security-Policy are set on every response.
- **Secret key enforcement** — `SECRET_KEY` is required in production; the app refuses to start without it.
- **File upload restrictions** — Only audio files (MP3, WAV, OGG, M4A, AAC) up to 16 MB are accepted.
- **Session-based auth** — Every route verifies the logged-in user before serving data.

---

## Contributing

Contributions are welcome! Please read the [Contributing Guidelines](CONTRIBUTING.md) and [Code of Conduct](CODE_OF_CONDUCT.md) before submitting a pull request.

---

## Future Enhancements

- Email notifications for reminders
- Pomodoro study timer integration
- Shared study groups and collaborative tasks
- Export notes to PDF or text
- Light/dark theme toggle
- Automated goal tracking
- Advanced analytics and reporting
- Browser notifications for reminders
- Data backup and export (JSON/CSV)
- Recurring task support

---

## License

This project is licensed under the [MIT License](LICENSE). You are free to use, modify, and distribute it.

---

## Contact

For questions, feedback, or contributions, please open an issue in the repository or reach out to the project maintainer.

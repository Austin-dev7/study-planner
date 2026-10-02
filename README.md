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
| Python 3.12+ | Programming language |
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
git clone https://github.com/Austin-dev7/study-planner.git
cd study-planner
```

2. Create and activate a virtual environment:

```bash
python -m venv venv
```

**Windows:**

```bash
venv\Scripts\activate
```

**macOS / Linux:**

```bash
source venv/bin/activate
```

3. Install the dependencies:

```bash
pip install -r requirements.txt
```

4. Start the application:

```bash
python run.py
```

The app opens automatically in your browser at `http://127.0.0.1:5000`.

---

## Running the Application

| Command | Purpose |
|---|---|
| `python run.py` | Start the server and open the browser |
| `python run_tests.py` | Run the smoke test suite |
| `python set_password.py` | Set a user's password from the command line |
| `python reset_user_password.py` | Reset a forgotten password |

---

## Creating a User Account

1. Open `http://127.0.0.1:5000`
2. Click **Register**
3. Enter a name, email address, and a password of at least 6 characters
4. Log in with those credentials

### Demo Account

A pre-seeded demo account is available for trying the app without registering:

- **Email:** `demo@studyplanner.app`
- **Password:** `demo123`

Or visit `/demo` to sign in instantly.

> **Note:** On Vercel without a configured database, demo data is regenerated on
> every cold start, so any changes you make are temporary.

---

## Usage Guide

1. **Dashboard** — review today's tasks, completed work, study hours, and upcoming deadlines
2. **Tasks** — add, edit, filter, complete, or delete tasks
3. **Calendar** — browse your month and spot busy days
4. **Statistics** — review weekly study hours, task status, and subject distribution
5. **Notes** — capture and search study notes
6. **Settings** — update your profile, change your password, manage subjects, and upload reminder sounds

Log study time from the dashboard using the **Log Study Time** button to feed the
weekly statistics chart.

---

## Project Structure

```
study-planner/
├── app.py                  # Flask application, routes, and database layer
├── api/
│   └── index.py            # Vercel serverless entry point
├── templates/              # Jinja2 HTML templates
├── static/
│   ├── css/style.css       # Stylesheet
│   └── js/main.js          # Frontend logic
├── run.py                  # Local launcher
├── run_tests.py            # Smoke tests
├── set_password.py         # CLI password setter
├── reset_user_password.py  # CLI password reset
├── vercel.json             # Vercel build configuration
└── requirements.txt
```

---

## Troubleshooting

**`RuntimeError: SECRET_KEY environment variable must be set in production`**
Set a `SECRET_KEY` environment variable. Generate one with:

```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

**`no such table: users`**
The database has not been initialised. Delete `study_planner.db` and restart the
app — the schema and demo data are created automatically on first run.

**`Address already in use`**
Port 5000 is occupied. Stop the other process, or edit `PORT` in `run.py`.

**Charts or statistics are empty**
Log some study time from the dashboard, then revisit **Statistics**.

**Reminder sounds fail to upload on Vercel**
File uploads are intentionally disabled on Vercel because the filesystem is
read-only and reset on each deployment. Upload sounds when running locally.

---

## Deploying to Vercel

The app is ready to deploy. Connect the repository at
<https://github.com/Austin-dev7/study-planner> to Vercel and add these
**environment variables** under *Settings → Environment Variables*:

| Variable | Required | Description |
|---|---|---|
| `SECRET_KEY` | Yes | Session signing key. Generate with `python -c "import secrets; print(secrets.token_hex(32))"` |
| `DATABASE_URL` | Recommended | PostgreSQL connection string. Without it the app falls back to SQLite in `/tmp`, which is **erased on every cold start** |
| `COOKIE_SECURE` | Recommended | Set to `1` so session cookies are only sent over HTTPS |

### Database behaviour

| `DATABASE_URL` set | Database | Durability |
|---|---|---|
| Yes | PostgreSQL | Data persists across deployments |
| No | SQLite in the system temp directory | Demo works, but all data resets on restart |

Attach a free PostgreSQL instance from the Vercel dashboard (Storage → Create
Database) or from a provider such as Neon or Supabase, then copy its connection
string into `DATABASE_URL`.

---

## Security

- Passwords hashed with Werkzeug (scrypt), never stored in plain text
- CSRF protection on all forms via Flask-WTF
- Login rate limiting via Flask-Limiter
- Session cookies marked `HttpOnly` and `SameSite=Lax`, and `Secure` when `COOKIE_SECURE=1`
- Security headers on every response: `X-Content-Type-Options`, `X-Frame-Options`, `Referrer-Policy`, and a Content Security Policy
- File uploads restricted by extension and rejected entirely on Vercel

To report a vulnerability, please open a GitHub issue rather than a public pull request.

---

## Contributing

Contributions are welcome. Please read [CONTRIBUTING.md](CONTRIBUTING.md) and the
[Code of Conduct](CODE_OF_CONDUCT.md) first.

---

## Future Enhancements

- Spaced-repetition review for notes
- Export tasks and notes to CSV or PDF
- Email notifications for reminders
- Dark mode
- Weekly progress email digest

---

## License

Released under the [MIT License](LICENSE).

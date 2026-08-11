import sqlite3
import secrets
import shutil
import os
import sys

DB = 'study_planner.db'
EMAIL = os.environ.get('USER_EMAIL', '')

if not EMAIL:
    print('Please set the USER_EMAIL environment variable, e.g.:')
    print('  set USER_EMAIL=you@example.com')
    print('  python reset_user_password.py')
    sys.exit(3)

# Backup DB
bak = DB + '.bak'
if os.path.exists(DB):
    shutil.copyfile(DB, bak)
    print(f'Backup created: {bak}')
else:
    print(f'Database file not found: {DB}')
    raise SystemExit(1)

# Generate a secure temporary password
new_password = secrets.token_urlsafe(10)

# Update the user's password (stored in plaintext in this app)
conn = sqlite3.connect(DB)
cur = conn.cursor()
cur.execute('SELECT id,email FROM users WHERE email = ?', (EMAIL,))
user = cur.fetchone()
if not user:
    print(f'User not found: {EMAIL}')
    conn.close()
    raise SystemExit(2)

cur.execute('UPDATE users SET password = ? WHERE email = ?', (new_password, EMAIL))
conn.commit()
print(f'Password for {EMAIL} has been reset.')
print('Temporary password:', new_password)
conn.close()

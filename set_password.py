"""
Password recovery helper for Study Planner.

Usage:
    python set_password.py <email> <new_password>

Example:
    python set_password.py you@example.com MyNewPass123!
"""

import sqlite3
import sys
import shutil
import os
from werkzeug.security import generate_password_hash

DB = 'study_planner.db'


def main():
    if len(sys.argv) != 3:
        print(__doc__)
        sys.exit(1)

    email = sys.argv[1]
    new_password = sys.argv[2]

    # Create a safety backup before modifying
    bak = DB + '.bak'
    if os.path.exists(DB):
        shutil.copyfile(DB, bak)
        print(f'Backup created: {bak}')

    conn = sqlite3.connect(DB)
    cur = conn.cursor()

    # Check the user exists
    cur.execute('SELECT id, email, name FROM users WHERE email = ?', (email,))
    user = cur.fetchone()
    if not user:
        print(f'User not found: {email}')
        conn.close()
        sys.exit(2)

    # Store a secure hash of the password
    hashed = generate_password_hash(new_password)
    cur.execute('UPDATE users SET password = ? WHERE email = ?', (hashed, email))
    conn.commit()

    cur.execute('SELECT id, email, name FROM users WHERE email = ?', (email,))
    row = cur.fetchone()
    print(f'Password updated for: {row[0]} - {row[1]} ({row[2]})')
    print('(Stored as a secure hash)')
    conn.close()


if __name__ == '__main__':
    main()


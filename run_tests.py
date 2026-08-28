"""
Simple smoke tests for Study Planner core routes using Flask test client.
Run with: python run_tests.py
"""
from app import app, get_db
from werkzeug.security import generate_password_hash
from io import BytesIO

# Testing configuration
app.config['WTF_CSRF_ENABLED'] = False
app.testing = True

client = app.test_client()

results = []

def expect_get(path, expected=200):
    r = client.get(path)
    ok = r.status_code == expected
    print(f"GET {path} -> {r.status_code} {'OK' if ok else 'FAIL'}")
    results.append(ok)


def expect_post(path, data=None, expected=200, follow_redirects=False, files=None):
    if files:
        r = client.post(path, data=data or {}, content_type='multipart/form-data', data_stream=None, follow_redirects=follow_redirects, buffered=True, files=files)
    else:
        r = client.post(path, data=data or {}, follow_redirects=follow_redirects)
    ok = r.status_code == expected
    print(f"POST {path} -> {r.status_code} {'OK' if ok else 'FAIL'}")
    results.append(ok)
    return r


def expect_post_json(path, data, expected):
    r = client.post(path, json=data)
    ok = r.status_code == expected
    try:
        payload = r.get_json()
    except Exception:
        payload = None
    print(f"POST {path} -> {r.status_code} {'OK' if ok else 'FAIL'} | json={payload}")
    results.append(ok)
    return r


def create_test_user(email='test@example.com', password='testpass'):
    conn = get_db()
    # Remove any existing test user
    conn.execute('DELETE FROM users WHERE email = ?', (email,))
    hashed = generate_password_hash(password)
    conn.execute('INSERT INTO users (email, password, name) VALUES (?, ?, ?)', (email, hashed, 'Tester'))
    conn.commit()
    conn.close()


if __name__ == '__main__':
    print('Running expanded tests...')

    # Basic GET endpoints
    expect_get('/login', 200)
    expect_get('/register', 302)
    expect_get('/', 302)

    # Create a test user and log in
    create_test_user()
    r = client.post('/login', data={'email': 'test@example.com', 'password': 'testpass'}, follow_redirects=True)
    ok = r.status_code == 200 and b'Dashboard' in r.data
    print(f"Login -> {r.status_code} {'OK' if ok else 'FAIL'}")
    results.append(ok)

    # Check reminders (should be allowed for logged-in user)
    r = expect_post_json('/api/check-reminders', {}, 200)

    # Create a task via form POST
    task_data = {
        'title': 'Test Task',
        'subject': 'Testing',
        'priority': 'High',
        'due_date': '2099-12-31',
        'description': 'Created by tests'
    }
    r = client.post('/add_task', data=task_data, follow_redirects=True)
    ok = r.status_code == 200 and b'Test Task' in r.data
    print(f"Add Task -> {r.status_code} {'OK' if ok else 'FAIL'}")
    results.append(ok)

    # Verify task appears on tasks page
    r = client.get('/tasks')
    ok = r.status_code == 200 and b'Test Task' in r.data
    print(f"Tasks List -> {r.status_code} {'OK' if ok else 'FAIL'}")
    results.append(ok)

    # Summary
    passed = sum(1 for r in results if r)
    total = len(results)
    print('\nSummary: {}/{} tests passed'.format(passed, total))
    if passed != total:
        raise SystemExit(1)
    else:
        print('All tests passed.')

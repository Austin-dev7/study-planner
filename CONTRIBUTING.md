# Contributing to Study Planner

Thank you for your interest in contributing! We welcome bug fixes, feature requests, documentation improvements, and new ideas.

## How to Contribute

### 1. Report a Bug
- Open an [issue](../../issues) and describe the bug clearly.
- Include steps to reproduce, expected behavior, and actual behavior.
- Share your environment (OS, Python version, browser) if relevant.

### 2. Request a Feature
- Open an [issue](../../issues) with the `feature` label.
- Explain the motivation and the value it adds.

### 3. Submit Code
1. **Fork** the repository and create a new branch:
   ```bash
   git checkout -b feature/my-feature
   ```
2. **Make your changes** following the code style below.
3. **Test** your changes locally.
4. **Commit** with a clear message:
   ```bash
   git commit -m "Add feature: description"
   ```
5. **Push** and open a Pull Request:
   ```bash
   git push origin feature/my-feature
   ```

## Development Setup

```bash
python -m venv venv
venv\Scripts\activate   # Windows
source venv/bin/activate   # macOS / Linux

pip install -r requirements.txt
python run.py
```

## Code Style

- Follow [PEP 8](https://peps.python.org/pep-0008/) for Python.
- Use meaningful variable and function names.
- Keep functions small and focused on a single responsibility.
- Add comments for non-obvious logic.
- Keep HTML templates readable and consistent with existing markup.

## Security Notes

- Never commit real passwords, secrets, or database files.
- Passwords must be hashed (Werkzeug) — never store plaintext.
- All new data-modifying routes should be protected with CSRF.
- Add rate limiting to any new public endpoints where appropriate.

## Testing

Before submitting, verify:
- The app starts with `python run.py`.
- Login, registration, and logout work.
- Core features (tasks, notes, calendar, statistics, settings) function correctly.
- No sensitive data is accidentally committed.

## Questions?

Feel free to open an issue or reach out to the maintainer. Happy coding!

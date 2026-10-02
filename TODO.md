# Study Planner - Security Hardening & Deployment TODOs

## Security Hardening ✅
- [x] Add CSRF protection to all forms
- [x] Add login rate limiting
- [x] Harden session cookies (HttpOnly, Secure, SameSite)
- [x] Require SECRET_KEY from env in production
- [x] Add security headers
- [x] Migrate plaintext passwords to hashed (werkzeug)

## Vercel Deployment ✅
- [x] Create `vercel.json` config
- [x] Create `api/index.py` serverless entry point
- [x] Update `requirements.txt`
- [x] Update `.gitignore` for Vercel
- [x] Stop import-time crashes on a read-only filesystem (uploads dir, SQLite path)
- [x] Fall back to SQLite in the temp directory when `DATABASE_URL` is absent
- [x] Fix Postgres `text >= date` crash on Dashboard and Statistics
- [x] Fix misplaced `500.html` that broke the error handler
- [ ] Add `SECRET_KEY` and `DATABASE_URL` in Vercel project settings

## Open Source Preparation ✅
- [x] Create `CONTRIBUTING.md`
- [x] Create `LICENSE` (MIT)
- [x] Create `CODE_OF_CONDUCT.md`
- [x] Update README with deployment + security

## Testing ✅
- [x] Verify app runs with Vercel entry point
- [x] Test login still works (end-to-end tested)
- [x] Verify server starts
- [x] Run smoke suite locally and under simulated Vercel env (7/7)
- [x] Verify custom 404 and 500 pages render

## Dashboard Enhancements ✅
- [x] Add "Total Tasks" stat card
- [x] Add "Overdue" stat card (with red highlight)
- [x] Add "Log Study Time" button + modal
- [x] Add `/api/study-sessions` route to record study hours
- [x] Add `.stat-icon.red` CSS class

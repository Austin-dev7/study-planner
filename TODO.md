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

## Open Source Preparation ✅
- [x] Create `CONTRIBUTING.md`
- [x] Create `LICENSE` (MIT)
- [x] Create `CODE_OF_CONDUCT.md`
- [x] Update README with deployment + security

## Testing ✅
- [x] Verify app runs with Vercel entry point
- [x] Test login still works (end-to-end tested)
- [x] Verify server starts

## Dashboard Enhancements ✅
- [x] Add "Total Tasks" stat card
- [x] Add "Overdue" stat card (with red highlight)
- [x] Add "Log Study Time" button + modal
- [x] Add `/api/study-sessions` route to record study hours
- [x] Add `.stat-icon.red` CSS class

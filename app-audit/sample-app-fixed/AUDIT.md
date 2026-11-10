# AUDIT - NoteBox (sample app)

- Date: 2026-11-10
- Commit / version: audited before the repo existed (first commit holds the result)
- Audited by: Claude Code, skill `app-audit`
- Scope: `sample-app/` (before) -> `sample-app-fixed/` (after). Run on `http://127.0.0.1` only. Test users: alice (A), bob (B). No admin role in this app.
- Tests before audit: 3 passed, 0 failed - after: 12 passed, 0 failed

File and line numbers point to **`sample-app/`** (the code before the fixes).

## Summary

| severity | found | fixed | open |
|---|---|---|---|
| critical | 2 | 2 | 0 |
| high | 6 | 6 | 0 |
| medium | 6 | 5 | 1 |
| low | 4 | 2 | 2 |

Top 3 things to know:

1. Anyone could log in as alice without a password (`' OR '1'='1' --` in the login form).
2. Bob could read Alice's notes by changing the number in the URL.
3. Two secrets were in the code. Code fix is done, but **secrets that were in code must be replaced** (see section 6).

## 1. App map

Stack: Python 3.10, Flask 3.1, server-rendered HTML (no REST/GraphQL API), SQLite, cookie session login.
No cache, CDN, background jobs or monitoring exist in this app.

| methods | path | page / API | needs login? | owner check? | file:line |
|---|---|---|---|---|---|
| GET | `/` | page | no | n/a | app.py:50 |
| GET, POST | `/login` | page + form | no | n/a | app.py:55 |
| GET | `/logout` | action | no | n/a | app.py:71 |
| GET, POST | `/notes` | page + 2 forms | yes | yes (`user_id = ?`) | app.py:77 |
| GET | `/notes/<id>` | page | yes | **NO** -> F-04 | app.py:96 |

Counts: 4 pages, 0 API endpoints, 3 forms, 5 buttons, 8 links (4 in the menu on every page).

## 2. UI click test (desktop 1440px + phone 390px)

Every row was seen at **both** sizes. Before: 56 checks, 10 bug rows. After: 26 checks, 0 bug rows.

| screen | element | expected | result | fixed? |
|---|---|---|---|---|
| /notes | button "Export notes" | does something when clicked | NOTHING happens: no navigation, no request, no page change | yes - now a link that downloads `notes.txt` |
| /notes | buttons "Save" / "Save note" | each button does a different job | DUPLICATE: 2 buttons submit the same form with the same data | yes - one button left |
| all pages | link "Pricing" -> /pricing | opens a page | HTTP 404 | yes - link removed (page never existed) |
| /login | form POST /login | has a hidden CSRF token field | no CSRF token field seen | yes (F-06) |
| /notes | form POST /notes | has a hidden CSRF token field | no CSRF token field seen | yes (F-06) |
| all pages | `<html>` | has a lang attribute | missing lang | yes |
| /login, /notes | fields username, password, q, title, body | has a label | no `<label>` (placeholder is not a label) | yes |
| all pages (phone) | menu links | at least 24px tall | 18px tall (seen after the first fixes) | yes |

No console errors and no sideways scroll at either size, before or after.

## 3. Findings

| ID | severity | title | file:line | proof (how it was seen) | fix | fixed? | re-test result |
|---|---|---|---|---|---|---|---|
| F-01 | critical | SQL injection in login (login without password) | app.py:61 | `probe_inputs.py` on POST /login: always-true input got HTTP 302 to /notes, always-false got 200. A single quote gave HTTP 500 `sqlite3.OperationalError` | Parameterized query `WHERE username = ?` | yes | Same probe: "PASS" for username and password. Test `test_f01` passes |
| F-03 | critical | Secrets in code: Flask session key and a payment API key | app.py:12, app.py:13 (`note...`, `nbx_...`) | `scan_code.py`: 2 SECRET hits. With the session key anyone can forge a login cookie | Key read from env `NOTEBOX_SECRET_KEY`; unused API key removed; `.env.example` + `.gitignore` added | yes (code) | `scan_code.py`: 0 leads. **Rotation is still your job** (section 6) |
| F-02 | high | XSS: reflected in search, stored in note body | templates/notes.html:9, templates/note.html:4 | `probe_inputs.py`: marker tag came back unescaped on `/notes?q=` and on the new note page | Removed `\|safe`; CSP header added as a second wall | yes | Same probes: "PASS". Test `test_f02` passes |
| F-04 | high | Broken access control: any user can read any note | app.py:100 | `access_check.py`: bob got HTTP 200 on `/notes/1` with Alice's text | Query is now `WHERE id = ? AND user_id = ?`, else 404 | yes | Same check: bob gets 404, verdict PASS. Test `test_f04` passes |
| F-05 | high | Passwords stored and compared as plain text | app.py:40, app.py:61 | Read the schema and the query; `scan_code.py` AUTH hit | `generate_password_hash` / `check_password_hash` (scrypt) | yes | Test `test_f05`: no password text in the users table |
| F-06 | high | No CSRF protection on any form; logout by GET | app.py:55-93, app.py:71 | Click test: no token field. POST without token was accepted | Per-session token, checked on every POST; logout is now a POST form | yes | `curl -X POST /notes` without token -> HTTP 400. GET /logout -> 405. Test `test_f06` passes |
| F-07 | high | No login lockout or rate limit | app.py:55 | `check_http.py --lockout-test 12`: never blocked | 5 wrong tries per IP + username -> HTTP 429 for 5 minutes | yes | Same test: "blocked after 6 tries". Test `test_f07` passes |
| F-08 | high | Debug mode on: stack trace and debugger page shown to users | app.py:109 | `probe_inputs.py`: "error page leaks details" (Werkzeug debugger on the 500 page) | Debug only when `NOTEBOX_DEBUG=1` | yes | Probe shows no leak row; `scan_code.py` 0 leads |
| F-09 | medium | Missing security headers (CSP, nosniff, frame, referrer, permissions) | app.py (no header code) | `check_http.py`: 5 FAIL rows per page | `after_request` adds all five; inline CSS moved to `static/style.css` so CSP can be strict | yes | `check_http.py`: all header rows PASS |
| F-10 | medium | Session cookie without SameSite; session not renewed at login | app.py:64 | `check_http.py`: SameSite missing | `SameSite=Lax`, HttpOnly, 8 h lifetime, `session.clear()` at login, `Secure` when `NOTEBOX_HTTPS=1` | yes | `check_http.py`: SameSite PASS. Secure flag: see NOT VERIFIED |
| F-11 | medium | Dead button, duplicate button, dead link | templates/notes.html:17, :23-24, templates/base.html:18 | Click test rows in section 2 | See section 2 | yes | Click test: 0 bug rows at both sizes |
| F-12 | medium | No server-side input validation (empty title, unlimited length) | app.py:80-86 | Read the code: values go straight to the database | Title needed, max 120; note max 10000; request body max 64 KB | yes | Manual read + existing tests pass. No own test written for this one |
| F-13 | medium | No logging of logins or denied access | app.py | `map_app.py`: logging NOT FOUND | Log login ok / failed / locked, CSRF fail, note-not-owned | yes | Read the code. Log output not checked by a test |
| F-14 | medium | No migrations: tables are dropped and re-made by `init_db()` | app.py:31 | Read the code | Not fixed (design choice for a demo). Real app: use Alembic or similar | no | - |
| F-15 | low | Accessibility: no labels, no `lang` | templates/base.html:2, login.html:6-7, notes.html:6,21,22 | Click test a11y rows | Labels and `lang="en"` added, bigger tap targets | yes | Click test: 0 a11y rows |
| F-16 | low | Dependencies not pinned | requirements.txt:1 | `flask>=3.0`, no lock file | Exact versions pinned | yes | See NOT VERIFIED for the vulnerability scan |
| F-17 | low | Server header shows versions (`Werkzeug/3.1.9 Python/3.10.12`) | Flask dev server | `check_http.py` | Not fixed: comes from the dev server. A real deploy uses gunicorn behind nginx/Caddy | no | - |
| F-18 | low | No README, no CI for the app itself, no privacy page | project root | `map_app.py` hygiene table | Not fixed (demo app) | no | - |

### Details: F-01

Before:

```python
query = f"SELECT * FROM users WHERE username = '{username}' AND password = '{password}'"
```

Typing `' OR '1'='1' -- ` as username turns the query into "give me any user". The app logged the visitor in as the first user (alice).

After:

```python
user = db().execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
if user and check_password_hash(user["password_hash"], typed):
```

## 4. Checklist result

| ID | check | result |
|---|---|---|
| B1 | Language and framework | PASS - Python 3.10, Flask 3.1.3 (both supported) |
| B2 | API layer | NOT APPLICABLE - no REST/GraphQL, only HTML forms |
| B3 | Database | PASS for the demo - SQLite file, not on the network |
| B4 | Indexes | FINDING fixed - `notes.user_id` had no index; added `idx_notes_user` |
| B5 | Migrations | FINDING F-14 (open) |
| B6 | Authentication | FINDING F-05, F-07 (fixed). No password reset or signup exists |
| B7 | Authorization | FINDING F-04 (fixed) |
| B8 | Encryption in transit | NOT VERIFIED - local http only |
| B9 | Encryption at rest | NOT VERIFIED - depends on the host disk. SQLite file is not encrypted |
| B10 | SQL injection | FINDING F-01 (fixed). All 5 queries read: all use parameters now |
| B11 | XSS | FINDING F-02 (fixed) |
| B12 | CSRF | FINDING F-06 (fixed) |
| B13 | Caching | PASS after fix - logged-in pages send `Cache-Control: no-store` |
| B14 | CDN | NOT APPLICABLE - no CDN, no outside scripts |
| B15 | Background jobs | NOT APPLICABLE - none |
| B16 | Logging and monitoring | FINDING F-13 (logging fixed). Monitoring/alerts: none (demo) |
| B17 | Backups and recovery | NOT VERIFIED - demo app, no real data, no backup exists |
| S1 | Input validation | FINDING F-12 (fixed) |
| S2 | Rate limit and lockout | FINDING F-07 (fixed for login). No other endpoint sends email or is costly |
| S3 | Security headers | FINDING F-09 (fixed). HSTS: NOT VERIFIED |
| S4 | Session and cookies | FINDING F-10 (fixed). Logout tested by unit test |
| S5 | Broken access control | FINDING F-04 (fixed). `/notes/export` checked by hand: only own notes (test `test_export_button_works`) |
| S6 | CORS | PASS - no CORS headers, unknown origin not trusted |
| S7 | File uploads | NOT APPLICABLE - no uploads |
| S8 | Secrets in code or git | FINDING F-03 (code fixed). Git history: see section 5 |
| S9 | Vulnerable dependencies | NOT VERIFIED in full (see section 5) |
| S10 | Error leaks | FINDING F-08 (fixed). 404 page was clean |
| S11 | Admin audit log | NOT APPLICABLE - no admin role |
| S12 | Open redirect / SSRF | PASS - all redirects go to fixed routes, no server-side fetch |
| S13 | Command injection / path / deserialization | PASS - `scan_code.py` 0 leads, code read |
| S14 | Misconfiguration | FINDING F-08 (fixed) |
| S15 | Data exposure in responses | PASS - pages show only the user's own notes |
| S16 | Business logic | PASS - nothing to cheat in a notes app |
| P1-P5 | GDPR basics | FINDING F-18 (no privacy page). No tracking cookies: only the session cookie was set |
| Q1 | Accessibility | FINDING F-15 (fixed). Keyboard-only use and colour contrast: NOT VERIFIED |
| Q2 | Page speed | PASS locally - every page under 30 ms and 3 KB |
| Q3 | Test coverage | 12 tests, one per fixed critical/high finding. Coverage % not measured |
| Q4 | CI | FINDING F-18 for the app. The skill repo has its own CI file |
| Q5 | UI at 1440 and 390 | FINDING F-11 (fixed) |
| Q6 | Project hygiene | Partly fixed: `.gitignore`, `.env.example` added |
| Z1 | State-changing GET | FINDING F-06 (logout by GET, fixed) |
| Z2 | Seed accounts with known passwords | FINDING noted: alice/bob test users. `init_db()` now only runs when `NOTEBOX_ENV=dev` |

## 5. NOT VERIFIED

| what | why not | how the owner can check it |
|---|---|---|
| Secrets in git history (at audit time) | The app was not a git repo during the audit. Checked later, after this repo was made: the history scan ran and reports the planted secrets of `sample-app/` (expected: that folder keeps them on purpose) and nothing for `sample-app-fixed/` | Nothing to do for the sample |
| HTTPS, HSTS, `Secure` cookie flag | App only ran on local http | Deploy with HTTPS, set `NOTEBOX_HTTPS=1`, run `check_http.py` on the https URL |
| Vulnerable dependencies (full scan) | `pip-audit -r requirements.txt` could not build its test environment here. Only a scan of the packages already installed on this machine ran: no known issue listed for Flask, Werkzeug, Jinja2, MarkupSafe, itsdangerous, click, blinker | Run `pip-audit -r requirements.txt` on your PC |
| Logout button in the real browser | The click test skips "log out" on purpose | Covered by unit test `test_logout_button_ends_the_session`; click it once by hand |
| Keyboard-only use, screen reader, colour contrast | Not automated | Tab through the pages; run Lighthouse |
| Lockout under real load / many servers | Lockout counter is in memory of one process | For a real app use Flask-Limiter with Redis |
| Encryption at rest, backups, monitoring | Demo app with no hosting | Decide when you host it |
| Real page speed | Local numbers only | Lighthouse on the deployed site |
| Phone layout by eye | Script checks overflow and tap size, nobody looked at screenshots | Open at 390px and look |

## 6. Your to-do list (things only you can do)

- [ ] Treat `note...` (session key) and `nbx_...` (payment key) as burned. In a real app: make new ones and revoke the old ones. (Here they are fake.)
- [ ] Set `NOTEBOX_SECRET_KEY` on the server. Without it the app makes a random key at each start and everyone is logged out on restart.
- [ ] Run `pip-audit -r requirements.txt`.

## 7. Added to the checklist during this audit

- Z1: state-changing GET links (found: logout by GET).
- Z2: seed / demo accounts with known passwords.

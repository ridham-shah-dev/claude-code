# app-audit

A Claude Code skill that audits **your own** app or website and fixes what it finds.

It maps the app, clicks every button on desktop and phone size, checks the backend
and security against an OWASP-based checklist, writes `AUDIT.md`, fixes the critical
and high problems, and tests each fix again.

Defensive use only: run it on code you own.

## What it does

1. **Maps the app** - pages, routes, API endpoints, buttons, forms, links.
2. **Clicks everything** in a real browser at 1440px and 390px. Finds dead buttons,
   duplicate buttons, dead links, broken forms, console errors.
3. **Checks the backend** - framework, API, database, indexes, migrations, login,
   permissions, encryption, SQL injection, XSS, CSRF, caching, CDN, jobs, logging, backups.
4. **Checks what is easy to forget** - input validation, rate limit and lockout,
   security headers, cookies, CORS, uploads, secrets in code and git history,
   dependencies, "can user A read user B's data?", error leaks, audit log, GDPR basics,
   accessibility, page speed, tests, CI. New gaps found in an audit are added to the
   checklist for next time.
5. **Writes `AUDIT.md`** - severity, file and line, fix, fixed yes/no.
6. **Fixes critical and high findings** and re-tests each one.
7. Lists everything it could not test under **NOT VERIFIED**.

## Install

Copy the skill folder into your Claude Code skills folder.

Windows (PowerShell):

```powershell
git clone https://github.com/ridham-shah-dev/app-audit.git
Copy-Item -Recurse app-audit\.claude\skills\app-audit $HOME\.claude\skills\
```

Linux / Mac:

```bash
git clone https://github.com/ridham-shah-dev/app-audit.git
cp -r app-audit/.claude/skills/app-audit ~/.claude/skills/
```

Needs Python 3.8+. For the click test also:

```bash
pip install playwright
python -m playwright install chromium
```

## Use

Open your project in Claude Code and type:

```
/app-audit
```

or just "audit my app". Use a dev database and test users: the click test really
clicks and submits forms.

## What is inside

```
.claude/skills/app-audit/
  SKILL.md              the steps Claude follows
  checklist.md          every check, how to test it, OWASP source
  report-template.md    the shape of AUDIT.md
  scripts/
    map_app.py          routes, forms, buttons, links from the code
    click_audit.py      real-browser click test, desktop + phone
    scan_code.py        risky code patterns, secrets in code and git history
    check_http.py       security headers, cookies, CORS, error leaks, login lockout
    access_check.py     can user B open user A's data?
    probe_inputs.py     confirms SQL injection and XSS on one form
sample-app/             small Flask app with planted bugs (do not deploy!)
sample-app-fixed/       the same app after the audit, with its AUDIT.md
tests/prove.py          proof that the skill finds every planted bug
```

You can also run each script by hand. Each one has `--help`.
The scripts that send requests only work on `localhost` unless you add `--i-own-this`.

## Proof

`sample-app/` has six planted bugs. `tests/prove.py` starts the app, runs the skill's
scripts and checks that each bug is found:

| planted bug | where | found by |
|---|---|---|
| dead button ("Export notes") | `templates/notes.html:17` | `click_audit.py`, both screen sizes |
| duplicate button ("Save" / "Save note") | `templates/notes.html:23-24` | `click_audit.py`, both screen sizes |
| SQL injection (login) | `app.py:61` | `scan_code.py` + confirmed live by `probe_inputs.py` |
| XSS (search and note body) | `templates/notes.html:9`, `note.html:4` | `scan_code.py` + confirmed live by `probe_inputs.py` |
| missing access check (bob reads alice's note) | `app.py:100` | `map_app.py` lead + confirmed live by `access_check.py` |
| secret in code | `app.py:12-13` | `scan_code.py` |

```bash
pip install flask playwright
python -m playwright install chromium
python tests/prove.py                                   # all six FOUND
python tests/prove.py sample-app-fixed --expect fixed   # all six GONE
```

The audit also found 12 more problems nobody planted (no CSRF, plain-text passwords,
debug mode, no lockout, missing headers, a dead link...). See
[sample-app-fixed/AUDIT.md](sample-app-fixed/AUDIT.md).

How the skill got better while testing it:

- The SQL scan missed f-strings with quotes inside. Fixed the pattern.
- The secret scan flagged `password = '{password}'` as a secret. Fixed.
- The stored-XSS probe only looked at the answer page. Now it opens the new item too.
- The XSS probe called a plain-text download "XSS". Now only HTML pages count.
- The click test called a file download a broken page. Now it is "gives a file".

## Limits (be honest)

- The scripts give **leads and proof**, Claude still has to read the code. A clean
  scan does not mean a safe app.
- Route and stack detection knows Flask, FastAPI, Express, Django, Laravel, Next.js
  and plain PHP/HTML best. It was only **proven** on the Flask sample app here.
- Only GET is tested for "user A reads user B's data". Edit and delete are checked by hand.
- HTTPS, HSTS, backups, hosting and monitoring cannot be tested on localhost.
  They go in NOT VERIFIED until you check the real server.
- This is not a penetration test and not legal advice for GDPR.

## Sources

- OWASP Top 10:2025 - https://owasp.org/Top10/2025/
- OWASP ASVS 5.0 - https://github.com/OWASP/ASVS
- OWASP Cheat Sheet Series - https://cheatsheetseries.owasp.org/
- WCAG 2.2 - https://www.w3.org/TR/WCAG22/

## License

MIT

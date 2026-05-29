# Contributing To BloodBank

Thanks for improving BloodBank. This is an academic/demo project, so changes should keep the app easy to run locally while still following clean engineering practices.

## Local Setup

```powershell
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
python app.py
```

Open `http://127.0.0.1:5000`.

## Development Checklist

- Keep database-backed behavior in API routes and service modules.
- Add or update tests for blood compatibility, eligibility, inventory, matching, or request workflows when those rules change.
- Keep demo data realistic and safe for an academic project.
- Do not commit `.env`, SQLite databases, logs, virtual environments, or generated cache files.
- Run tests before pushing:

```powershell
python -m unittest discover -s tests
```

## Suggested Branch Names

```text
feature/donor-profile
feature/request-matching
fix/inventory-transition
docs/setup-guide
```

## Pull Request Notes

Include:

- What changed
- Why it changed
- Screenshots for UI updates
- Test command output
- Any follow-up work


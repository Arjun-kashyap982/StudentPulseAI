# StudentPulse AI

A beginner-friendly Flask and SQLite career-readiness companion. Students maintain a profile, select a role, record skill proficiency and evidence, understand skill gaps, and track a personalized growth plan.

## Run on Windows

1. Install Python 3.10+.
2. Open PowerShell in this project folder.
3. Create and activate a virtual environment:

   ```powershell
   py -m venv .venv
   .\.venv\Scripts\Activate.ps1
   ```

4. Install dependencies and start the app:

   ```powershell
   python -m pip install -r requirements.txt
   python app.py
   ```

5. Open <http://127.0.0.1:5000>.

Flask creates `instance\studentpulse.sqlite3` and the clearly labeled demo account the first time the app starts. For local development, the built-in development secret is sufficient. Before deploying anywhere, set a private `SECRET_KEY` environment variable and turn off debug mode.

To restore the demo profile, sign in as the demo account and choose **Settings → Reset demo data**, or run:

```powershell
flask --app app reset-demo
```

### Faculty demo account

- **Email:** `demo@studentpulse.ai`
- **Password:** `Demo1234!`

The demo profile name, certificate issuer, project URLs, and activity are explicitly sample/demo information. Links use `example.com` and do not claim to be real credentials or hosted work.

## Features

- Registration, login, logout, Werkzeug password hashing, and account-scoped data.
- Student profile (including programming languages), career-goal selection, role requirements, and proficiency/evidence management.
- Skills CRUD, including edit and delete.
- Transparent gap analysis with strong, developing, and missing skill categories.
- Rules-based recommendations grounded in role requirements, recorded skills, and project evidence.
- Generated starter growth plans, editable custom tasks, priorities, estimates, completion tracking, and activity history.
- Add/edit/remove projects and certifications; profile data is used as career evidence.
- Data-backed dashboard and analytics charts for skill alignment and task completion.
- Responsive dark dashboard, status messages, confirmation dialogs, and empty states.
- A labeled demo profile and reset workflow.

## Project structure

```text
app.py                    Flask entry point
studentpulse/
  __init__.py             App factory, setup, and CLI command
  db.py                   SQLite schema, role catalog, demo data, activity helpers
  routes.py               Authentication and application routes
  services.py             Readiness and recommendation calculations
templates/                Reusable Jinja templates for all pages
static/css/style.css      Responsive dark UI
static/js/app.js          Navigation, role selection, confirmations, flash behavior
static/images/            Locally hosted, responsive career and empty-state SVG illustrations
tests/test_app.py         Focused integration tests
instance/                 Local SQLite database (created at runtime; not committed)
```

## Readiness algorithm (viva explanation)

Each career pathway has a small, editable-in-code list of required skills and target levels. Beginner, Intermediate, and Advanced are represented as 1, 2, and 3. For each required skill:

`skill score = min(student level / target level, 1) × 100`

A missing skill has level 0 and therefore scores 0. Readiness is the arithmetic mean of the required-skill scores, rounded to the nearest whole percentage. A level above the target cannot earn more than 100% for that skill. A gap is **Strong** when the current level meets the target, **Developing** when it is present but below target, and **Missing** when it has not been recorded. A missing skill with a target of Intermediate or Advanced is marked High priority; other gaps are Medium. The gap page shows the reason each role skill matters.

Recommendations are deterministic rules, not generated intelligence: the app ranks skills below their target and suggests focused practice (or a small project if the student already has project evidence), then suggests creating a first portfolio project when none exists. The app does **not** call an external AI API. All suggestions are labeled **Rules-based**; there is no fake AI feature or API key requirement.

## Pages

Landing, registration, login, dashboard, profile, career goals, skills, skill gap analysis, growth plan, projects, certifications, progress & analytics, and settings. Protected pages require login.

## Tests

Run the integration tests with:

```powershell
python -m unittest discover -s tests -v
```

## Limitations and future work

- The role catalog and skill targets are starter examples, not labor-market research or professional certification standards.
- Self-reported proficiency and evidence are not independently verified; scores are guidance, not hiring predictions.
- Recommendations are transparent rules-based suggestions. Adding an optional external model would require privacy review, API-key management, and clearly labeled provenance.
- Chart.js and the typography are loaded from CDNs; data entry and server-rendered pages still work without those assets, but charts/fonts may not load offline.
- The application is intended for local demonstration. Production use would need CSRF protection, deployment-grade secret management, HTTPS, account recovery, stronger operational monitoring, and a reviewed privacy policy.

## Suggested viva demonstration

1. Sign in with the demo credentials and point out the DEMO PROFILE label.
2. Show the Software Developer pathway and its required skill target levels.
3. Open Skill Gap Analysis and explain the level ratio and arithmetic mean.
4. Add or edit a skill and show how the score and recommendation change.
5. Complete a growth task and show the dashboard and chart update from SQLite data.
6. Add a project/certification, then show the activity history and evidence.
7. Reset demo data from Settings and clarify that all suggestions are rules-based, not external AI output.

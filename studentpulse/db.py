import sqlite3
from datetime import date, timedelta
from pathlib import Path

from flask import current_app, g
from werkzeug.security import generate_password_hash


ROLE_SKILLS = {
    "Software Developer": [
        ("Python", 2, "Builds problem-solving and application development foundations."),
        ("Data Structures", 2, "Helps select efficient ways to organize and process data."),
        ("Git", 2, "Supports collaboration and safe version control."),
        ("SQL", 2, "Most applications need reliable data storage and retrieval."),
        ("Testing", 2, "Improves reliability and makes changes safer."),
        ("API Development", 2, "Connects applications to services and other systems."),
    ],
    "Data Analyst": [
        ("SQL", 2, "Retrieves and combines data for analysis."),
        ("Python", 2, "Automates analysis and data preparation."),
        ("Data Visualization", 2, "Communicates findings clearly to stakeholders."),
        ("Statistics", 2, "Helps distinguish meaningful patterns from noise."),
        ("Excel", 2, "Remains common for exploration and business reporting."),
        ("Data Cleaning", 2, "Reliable analysis depends on usable input data."),
    ],
    "Python Developer": [
        ("Python", 3, "The core language used to build Python applications."),
        ("Object-Oriented Programming", 2, "Helps structure maintainable applications."),
        ("SQL", 2, "Many Python services read and write persistent data."),
        ("Testing", 2, "Protects behavior as a codebase evolves."),
        ("Git", 2, "Tracks changes and supports team development."),
        ("API Development", 2, "Enables Python applications to expose useful services."),
    ],
    "Web Developer": [
        ("HTML/CSS", 2, "Creates the structure and presentation of web pages."),
        ("JavaScript", 2, "Adds interactive behavior in the browser."),
        ("API Development", 2, "Connects user interfaces to application data."),
        ("Git", 2, "Supports collaboration and dependable releases."),
        ("SQL", 1, "Useful for data-backed web applications."),
        ("Testing", 1, "Catches regressions in interactive experiences."),
    ],
    "AI/ML Engineer": [
        ("Python", 3, "The primary language in many machine-learning workflows."),
        ("Statistics", 2, "Supports sound model evaluation and interpretation."),
        ("Machine Learning", 2, "Core methods for learning patterns from data."),
        ("Data Cleaning", 2, "Model quality depends on the quality of its input data."),
        ("SQL", 1, "Often needed to source and prepare training data."),
        ("Git", 2, "Makes experiments and code changes traceable."),
    ],
}

ROLE_DESCRIPTIONS = {
    "Software Developer": "Design, build, test, and maintain software applications.",
    "Data Analyst": "Turn structured data into clear insights and decisions.",
    "Python Developer": "Build maintainable tools, services, and applications with Python.",
    "Web Developer": "Create accessible, responsive, data-backed web experiences.",
    "AI/ML Engineer": "Prepare data and build, evaluate, and integrate machine-learning systems.",
}


def get_db():
    if "db" not in g:
        database_path = current_app.config["DATABASE"]
        Path(database_path).parent.mkdir(parents=True, exist_ok=True)
        g.db = sqlite3.connect(database_path)
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db


def close_db(_error=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db():
    db = get_db()
    db.executescript(
        """
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT NOT NULL UNIQUE COLLATE NOCASE,
            password_hash TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS profiles (
            user_id INTEGER PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
            college TEXT NOT NULL DEFAULT '',
            degree TEXT NOT NULL DEFAULT '',
            year_semester TEXT NOT NULL DEFAULT '',
            career_goal TEXT NOT NULL DEFAULT '',
            programming_languages TEXT NOT NULL DEFAULT '',
            interests TEXT NOT NULL DEFAULT '',
            experience TEXT NOT NULL DEFAULT ''
        );
        CREATE TABLE IF NOT EXISTS role_skills (
            role TEXT NOT NULL,
            skill_name TEXT NOT NULL,
            target_level INTEGER NOT NULL CHECK(target_level BETWEEN 1 AND 3),
            explanation TEXT NOT NULL,
            PRIMARY KEY(role, skill_name)
        );
        CREATE TABLE IF NOT EXISTS skills (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            name TEXT NOT NULL,
            level INTEGER NOT NULL CHECK(level BETWEEN 1 AND 3),
            evidence TEXT NOT NULL DEFAULT '',
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(user_id, name COLLATE NOCASE)
        );
        CREATE TABLE IF NOT EXISTS projects (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            name TEXT NOT NULL,
            description TEXT NOT NULL DEFAULT '',
            technologies TEXT NOT NULL DEFAULT '',
            link TEXT NOT NULL DEFAULT '',
            completion_date TEXT NOT NULL DEFAULT ''
        );
        CREATE TABLE IF NOT EXISTS certifications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            name TEXT NOT NULL,
            issuer TEXT NOT NULL DEFAULT '',
            issue_date TEXT NOT NULL DEFAULT '',
            link TEXT NOT NULL DEFAULT ''
        );
        CREATE TABLE IF NOT EXISTS tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            role TEXT NOT NULL DEFAULT '',
            title TEXT NOT NULL,
            description TEXT NOT NULL DEFAULT '',
            skill_name TEXT NOT NULL DEFAULT '',
            priority TEXT NOT NULL DEFAULT 'Medium',
            estimated_minutes INTEGER NOT NULL DEFAULT 60,
            completed INTEGER NOT NULL DEFAULT 0 CHECK(completed IN (0, 1)),
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            completed_at TEXT
        );
        CREATE TABLE IF NOT EXISTS activities (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            message TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        """
    )
    profile_columns = {
        row["name"] for row in db.execute("PRAGMA table_info(profiles)").fetchall()
    }
    if "programming_languages" not in profile_columns:
        db.execute(
            "ALTER TABLE profiles ADD COLUMN programming_languages TEXT NOT NULL DEFAULT ''"
        )
    for role, skills in ROLE_SKILLS.items():
        db.executemany(
            "INSERT OR IGNORE INTO role_skills(role, skill_name, target_level, explanation) "
            "VALUES (?, ?, ?, ?)",
            [(role, name, target, explanation) for name, target, explanation in skills],
        )
    db.commit()


def log_activity(user_id, message):
    db = get_db()
    db.execute("INSERT INTO activities(user_id, message) VALUES (?, ?)", (user_id, message))
    db.commit()


def create_growth_plan(user_id, role):
    db = get_db()
    existing = db.execute(
        "SELECT COUNT(*) AS count FROM tasks WHERE user_id = ? AND role = ?",
        (user_id, role),
    ).fetchone()["count"]
    if existing:
        return
    requirements = db.execute(
        "SELECT skill_name FROM role_skills WHERE role = ? ORDER BY target_level DESC",
        (role,),
    ).fetchall()
    starter_tasks = [
        ("Review the fundamentals", "Study core concepts and make a short summary.", 60),
        ("Complete a focused practice set", "Solve small exercises and record what you learned.", 90),
        ("Build a portfolio mini-project", "Apply the skill in a small project and document the result.", 180),
    ]
    for index, (title, description, minutes) in enumerate(starter_tasks):
        skill = requirements[min(index, len(requirements) - 1)]["skill_name"]
        db.execute(
            "INSERT INTO tasks(user_id, role, title, description, skill_name, priority, estimated_minutes) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (user_id, role, title, description, skill, "High" if index == 0 else "Medium", minutes),
        )
    db.commit()


def seed_demo(reset=False):
    db = get_db()
    email = "demo@studentpulse.ai"
    user = db.execute("SELECT id FROM users WHERE email = ?", (email,)).fetchone()
    if user and not reset:
        return
    if user:
        user_id = user["id"]
        for table in ("activities", "tasks", "skills", "projects", "certifications"):
            db.execute(f"DELETE FROM {table} WHERE user_id = ?", (user_id,))
        db.execute(
            "UPDATE profiles SET college='', degree='', year_semester='', career_goal='', "
            "interests='', experience='' WHERE user_id = ?",
            (user_id,),
        )
    else:
        cursor = db.execute(
            "INSERT INTO users(name, email, password_hash) VALUES (?, ?, ?)",
            ("Aarav Sharma (Demo)", email, generate_password_hash("Demo1234!")),
        )
        user_id = cursor.lastrowid
        db.execute("INSERT INTO profiles(user_id) VALUES (?)", (user_id,))
    db.execute(
        "UPDATE profiles SET college=?, degree=?, year_semester=?, career_goal=?, "
        "programming_languages=?, interests=?, experience=? "
        "WHERE user_id=?",
        (
            "Northstar Institute of Technology",
            "MCA",
            "Year 2 · Semester 3",
            "Software Developer",
            "Python, JavaScript",
            "Open-source, product design, problem solving",
            "Student developer; completed academic and personal projects.",
            user_id,
        ),
    )
    sample_skills = [
        ("Python", 2, "Built a Flask student task tracker."),
        ("Git", 2, "Used branches and commits for class projects."),
        ("SQL", 1, "Designed SQLite tables for a coursework project."),
        ("HTML/CSS", 2, "Created responsive pages for a portfolio."),
        ("JavaScript", 1, "Added form validation and small UI interactions."),
        ("Data Structures", 1, "Practiced arrays, stacks, and basic complexity."),
    ]
    db.executemany(
        "INSERT INTO skills(user_id, name, level, evidence) VALUES (?, ?, ?, ?)",
        [(user_id, *skill) for skill in sample_skills],
    )
    db.executemany(
        "INSERT INTO projects(user_id, name, description, technologies, link, completion_date) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        [
            (
                user_id,
                "Campus Event Planner",
                "A small tool for browsing and organizing student events.",
                "Python, Flask, SQLite",
                "https://example.com/campus-event-planner",
                (date.today() - timedelta(days=70)).isoformat(),
            ),
            (
                user_id,
                "Personal Portfolio",
                "Responsive portfolio to present coursework and project notes.",
                "HTML, CSS, JavaScript",
                "https://example.com/aarav-portfolio",
                (date.today() - timedelta(days=35)).isoformat(),
            ),
        ],
    )
    db.execute(
        "INSERT INTO certifications(user_id, name, issuer, issue_date, link) VALUES (?, ?, ?, ?, ?)",
        (
            user_id,
            "Python Essentials",
            "Open Learning Academy (sample)",
            (date.today() - timedelta(days=50)).isoformat(),
            "https://example.com/sample-certificate",
        ),
    )
    create_growth_plan(user_id, "Software Developer")
    task_ids = db.execute(
        "SELECT id FROM tasks WHERE user_id=? ORDER BY id LIMIT 3", (user_id,)
    ).fetchall()
    if task_ids:
        db.execute(
            "UPDATE tasks SET completed=1, completed_at=? WHERE id=?",
            (date.today().isoformat(), task_ids[0]["id"]),
        )
    for message in (
        "Demo profile and Software Developer goal set up.",
        "Added Campus Event Planner to project evidence.",
        "Completed a focused skill review.",
    ):
        db.execute("INSERT INTO activities(user_id, message) VALUES (?, ?)", (user_id, message))
    db.commit()

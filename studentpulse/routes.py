import sqlite3
from datetime import date
from functools import wraps
from urllib.parse import urlparse

from flask import (
    Blueprint,
    abort,
    flash,
    g,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from werkzeug.security import check_password_hash, generate_password_hash

from .db import ROLE_DESCRIPTIONS, ROLE_SKILLS, create_growth_plan, get_db, log_activity, seed_demo
from .services import LEVEL_LABELS, analyze_readiness, dashboard_data, get_profile, recommendations

main = Blueprint("main", __name__)


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if "user_id" not in session:
            flash("Please log in to continue.", "info")
            return redirect(url_for("main.login"))
        g.user = get_db().execute(
            "SELECT id, name, email FROM users WHERE id=?", (session["user_id"],)
        ).fetchone()
        if not g.user:
            session.clear()
            return redirect(url_for("main.login"))
        return view(*args, **kwargs)

    return wrapped


def safe_external_url(value):
    value = value.strip()
    if not value:
        return ""
    parsed = urlparse(value)
    return value if parsed.scheme in {"http", "https"} and parsed.netloc else None


def clean_text(field, label, maximum=300):
    value = request.form.get(field, "").strip()
    if len(value) > maximum:
        raise ValueError(f"{label} must be {maximum} characters or fewer.")
    return value


def user_owned(table, record_id):
    row = get_db().execute(
        f"SELECT * FROM {table} WHERE id=? AND user_id=?", (record_id, session["user_id"])
    ).fetchone()
    if not row:
        abort(404)
    return row


@main.route("/")
def landing():
    if "user_id" in session:
        return redirect(url_for("main.dashboard"))
    return render_template("landing.html")


@main.route("/register", methods=("GET", "POST"))
def register():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        db = get_db()
        error = None
        if not name or len(name) > 80:
            error = "Enter a name between 1 and 80 characters."
        elif "@" not in email or len(email) > 254:
            error = "Enter a valid email address."
        elif len(password) < 8:
            error = "Password must contain at least 8 characters."
        elif db.execute("SELECT id FROM users WHERE email=?", (email,)).fetchone():
            error = "An account with that email already exists."
        if error:
            flash(error, "error")
        else:
            cursor = db.execute(
                "INSERT INTO users(name, email, password_hash) VALUES (?, ?, ?)",
                (name, email, generate_password_hash(password)),
            )
            user_id = cursor.lastrowid
            db.execute("INSERT INTO profiles(user_id) VALUES (?)", (user_id,))
            db.commit()
            session.clear()
            session["user_id"] = user_id
            log_activity(user_id, "Created a StudentPulse account.")
            flash("Your account is ready. Set a career goal to get started.", "success")
            return redirect(url_for("main.profile"))
    return render_template("auth.html", mode="register")


@main.route("/login", methods=("GET", "POST"))
def login():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        user = get_db().execute("SELECT * FROM users WHERE email=?", (email,)).fetchone()
        if user is None or not check_password_hash(user["password_hash"], password):
            flash("Email or password is incorrect.", "error")
        else:
            session.clear()
            session["user_id"] = user["id"]
            flash(f"Welcome back, {user['name'].split(' (')[0]}.", "success")
            return redirect(url_for("main.dashboard"))
    return render_template("auth.html", mode="login")


@main.post("/logout")
def logout():
    session.clear()
    flash("You have been logged out.", "info")
    return redirect(url_for("main.landing"))


@main.route("/dashboard")
@login_required
def dashboard():
    return render_template("dashboard.html", data=dashboard_data(g.user["id"]))


@main.route("/profile", methods=("GET", "POST"))
@login_required
def profile():
    db = get_db()
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        try:
            college = clean_text("college", "College")
            degree = clean_text("degree", "Degree", 100)
            year = clean_text("year_semester", "Year / semester", 100)
            languages = clean_text("programming_languages", "Programming languages", 300)
            interests = clean_text("interests", "Interests", 500)
            experience = clean_text("experience", "Experience", 1000)
            if not name or len(name) > 80:
                raise ValueError("Name must contain 1 to 80 characters.")
            db.execute("UPDATE users SET name=? WHERE id=?", (name, g.user["id"]))
            db.execute(
                "UPDATE profiles SET college=?, degree=?, year_semester=?, programming_languages=?, "
                "interests=?, experience=? "
                "WHERE user_id=?",
                (college, degree, year, languages, interests, experience, g.user["id"]),
            )
            db.commit()
            log_activity(g.user["id"], "Updated profile details.")
            flash("Profile saved.", "success")
            return redirect(url_for("main.profile"))
        except ValueError as exc:
            flash(str(exc), "error")
    return render_template("profile.html", profile=get_profile(g.user["id"]))


@main.route("/career", methods=("GET", "POST"))
@login_required
def career():
    db = get_db()
    profile_data = get_profile(g.user["id"])
    if request.method == "POST":
        role = request.form.get("career_goal", "")
        if role not in ROLE_SKILLS:
            flash("Choose one of the listed career pathways.", "error")
        else:
            previous = profile_data["career_goal"]
            db.execute("UPDATE profiles SET career_goal=? WHERE user_id=?", (role, g.user["id"]))
            db.commit()
            if previous != role:
                create_growth_plan(g.user["id"], role)
                log_activity(g.user["id"], f"Selected the {role} career pathway.")
            flash("Career goal saved and your growth path is ready.", "success")
            return redirect(url_for("main.career"))
    return render_template(
        "career.html",
        profile=profile_data,
        roles=ROLE_DESCRIPTIONS,
        role_skills=ROLE_SKILLS,
    )


@main.route("/skills", methods=("GET", "POST"))
@login_required
def skills():
    db = get_db()
    if request.method == "POST":
        action = request.form.get("action", "add")
        try:
            name = clean_text("name", "Skill name", 80)
            evidence = clean_text("evidence", "Evidence", 500)
            level = int(request.form.get("level", "1"))
            if not name or level not in (1, 2, 3):
                raise ValueError("Enter a skill name and a valid proficiency level.")
            if action == "edit":
                skill_id = int(request.form.get("skill_id", "0"))
                user_owned("skills", skill_id)
                db.execute(
                    "UPDATE skills SET name=?, level=?, evidence=?, updated_at=CURRENT_TIMESTAMP "
                    "WHERE id=? AND user_id=?",
                    (name, level, evidence, skill_id, g.user["id"]),
                )
                message = f"Updated the {name} skill."
            else:
                db.execute(
                    "INSERT INTO skills(user_id, name, level, evidence) VALUES (?, ?, ?, ?)",
                    (g.user["id"], name, level, evidence),
                )
                message = f"Added the {name} skill."
            db.commit()
            log_activity(g.user["id"], message)
            flash("Skill saved.", "success")
            return redirect(url_for("main.skills"))
        except ValueError as exc:
            flash("That skill could not be saved. Check the name, level, and duplicate entries.", "error")
        except sqlite3.IntegrityError:
            db.rollback()
            flash("A skill with that name already exists in your profile.", "error")
    current_skills = db.execute(
        "SELECT * FROM skills WHERE user_id=? ORDER BY name", (g.user["id"],)
    ).fetchall()
    return render_template("skills.html", skills=current_skills, labels=LEVEL_LABELS)


@main.post("/skills/<int:skill_id>/delete")
@login_required
def delete_skill(skill_id):
    skill = user_owned("skills", skill_id)
    db = get_db()
    db.execute("DELETE FROM skills WHERE id=? AND user_id=?", (skill_id, g.user["id"]))
    db.commit()
    log_activity(g.user["id"], f"Removed the {skill['name']} skill.")
    flash("Skill removed.", "success")
    return redirect(url_for("main.skills"))


@main.route("/gap-analysis")
@login_required
def gap_analysis():
    analysis = analyze_readiness(g.user["id"])
    return render_template(
        "gap.html",
        analysis=analysis,
        recommendations=recommendations(g.user["id"], analysis),
        labels=LEVEL_LABELS,
    )


@main.route("/growth-plan", methods=("GET", "POST"))
@login_required
def growth_plan():
    db = get_db()
    profile_data = get_profile(g.user["id"])
    if request.method == "POST":
        action = request.form.get("action", "add")
        if action == "add":
            title = request.form.get("title", "").strip()
            description = request.form.get("description", "").strip()
            skill_name = request.form.get("skill_name", "").strip()
            priority = request.form.get("priority", "Medium")
            try:
                minutes = int(request.form.get("estimated_minutes", "60"))
            except ValueError:
                minutes = 0
            if (
                not title
                or len(title) > 120
                or len(description) > 500
                or len(skill_name) > 80
                or priority not in {"High", "Medium", "Low"}
                or not 5 <= minutes <= 1440
            ):
                flash("Enter a valid task, priority, and estimate (5–1440 minutes).", "error")
            else:
                db.execute(
                    "INSERT INTO tasks(user_id, role, title, description, skill_name, priority, estimated_minutes) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (g.user["id"], profile_data["career_goal"], title, description, skill_name, priority, minutes),
                )
                db.commit()
                log_activity(g.user["id"], f"Added growth task: {title}.")
                flash("Growth task added.", "success")
                return redirect(url_for("main.growth_plan"))
        elif action == "toggle":
            task_id = int(request.form.get("task_id", "0"))
            task = user_owned("tasks", task_id)
            completed = 0 if task["completed"] else 1
            db.execute(
                "UPDATE tasks SET completed=?, completed_at=? WHERE id=? AND user_id=?",
                (completed, date.today().isoformat() if completed else None, task_id, g.user["id"]),
            )
            db.commit()
            log_activity(
                g.user["id"],
                f"{'Completed' if completed else 'Reopened'} growth task: {task['title']}.",
            )
            flash("Task progress updated.", "success")
            return redirect(url_for("main.growth_plan"))
        elif action == "edit":
            task_id = int(request.form.get("task_id", "0"))
            task = user_owned("tasks", task_id)
            title = request.form.get("title", "").strip()
            description = request.form.get("description", "").strip()
            skill_name = request.form.get("skill_name", "").strip()
            priority = request.form.get("priority", "Medium")
            try:
                minutes = int(request.form.get("estimated_minutes", "60"))
            except ValueError:
                minutes = 0
            if (
                not title
                or len(title) > 120
                or len(description) > 500
                or len(skill_name) > 80
                or priority not in {"High", "Medium", "Low"}
                or not 5 <= minutes <= 1440
            ):
                flash("Enter a valid task, priority, and estimate (5–1440 minutes).", "error")
            else:
                db.execute(
                    "UPDATE tasks SET title=?, description=?, skill_name=?, priority=?, estimated_minutes=? "
                    "WHERE id=? AND user_id=?",
                    (title, description, skill_name, priority, minutes, task_id, g.user["id"]),
                )
                db.commit()
                log_activity(g.user["id"], f"Updated growth task: {title}.")
                flash("Task updated.", "success")
                return redirect(url_for("main.growth_plan"))
        elif action == "delete":
            task_id = int(request.form.get("task_id", "0"))
            task = user_owned("tasks", task_id)
            db.execute("DELETE FROM tasks WHERE id=? AND user_id=?", (task_id, g.user["id"]))
            db.commit()
            log_activity(g.user["id"], f"Removed growth task: {task['title']}.")
            flash("Task removed.", "success")
            return redirect(url_for("main.growth_plan"))
    tasks = db.execute(
        "SELECT * FROM tasks WHERE user_id=? ORDER BY completed, "
        "CASE priority WHEN 'High' THEN 0 WHEN 'Medium' THEN 1 ELSE 2 END, id",
        (g.user["id"],),
    ).fetchall()
    return render_template(
        "growth_plan.html",
        tasks=tasks,
        profile=profile_data,
        analysis=analyze_readiness(g.user["id"]),
    )


@main.route("/projects", methods=("GET", "POST"))
@login_required
def projects():
    db = get_db()
    if request.method == "POST":
        action = request.form.get("action", "add")
        try:
            if action == "edit":
                project_id = int(request.form.get("project_id", "0"))
                user_owned("projects", project_id)
            name = clean_text("name", "Project name", 120)
            description = clean_text("description", "Description", 1000)
            technologies = clean_text("technologies", "Technologies", 250)
            link = safe_external_url(request.form.get("link", ""))
            completion_date = clean_text("completion_date", "Completion date", 10)
            if not name or link is None:
                raise ValueError("Enter a project name and a valid http(s) project link.")
            if action == "edit":
                db.execute(
                    "UPDATE projects SET name=?, description=?, technologies=?, link=?, completion_date=? "
                    "WHERE id=? AND user_id=?",
                    (name, description, technologies, link, completion_date, project_id, g.user["id"]),
                )
                activity = f"Updated project evidence: {name}."
            else:
                db.execute(
                    "INSERT INTO projects(user_id, name, description, technologies, link, completion_date) "
                    "VALUES (?, ?, ?, ?, ?, ?)",
                    (g.user["id"], name, description, technologies, link, completion_date),
                )
                activity = f"Added project evidence: {name}."
            db.commit()
            log_activity(g.user["id"], activity)
            flash("Project saved.", "success")
            return redirect(url_for("main.projects"))
        except ValueError as exc:
            flash(str(exc), "error")
    items = db.execute("SELECT * FROM projects WHERE user_id=? ORDER BY id DESC", (g.user["id"],)).fetchall()
    return render_template("projects.html", projects=items)


@main.post("/projects/<int:project_id>/delete")
@login_required
def delete_project(project_id):
    project = user_owned("projects", project_id)
    db = get_db()
    db.execute("DELETE FROM projects WHERE id=? AND user_id=?", (project_id, g.user["id"]))
    db.commit()
    log_activity(g.user["id"], f"Removed project evidence: {project['name']}.")
    flash("Project removed.", "success")
    return redirect(url_for("main.projects"))


@main.route("/certifications", methods=("GET", "POST"))
@login_required
def certifications():
    db = get_db()
    if request.method == "POST":
        action = request.form.get("action", "add")
        try:
            if action == "edit":
                certificate_id = int(request.form.get("certificate_id", "0"))
                user_owned("certifications", certificate_id)
            name = clean_text("name", "Certificate name", 120)
            issuer = clean_text("issuer", "Issuing organization", 120)
            issue_date = clean_text("issue_date", "Issue date", 10)
            link = safe_external_url(request.form.get("link", ""))
            if not name or link is None:
                raise ValueError("Enter a certificate name and a valid http(s) certificate link.")
            if action == "edit":
                db.execute(
                    "UPDATE certifications SET name=?, issuer=?, issue_date=?, link=? "
                    "WHERE id=? AND user_id=?",
                    (name, issuer, issue_date, link, certificate_id, g.user["id"]),
                )
                activity = f"Updated certification: {name}."
            else:
                db.execute(
                    "INSERT INTO certifications(user_id, name, issuer, issue_date, link) "
                    "VALUES (?, ?, ?, ?, ?)",
                    (g.user["id"], name, issuer, issue_date, link),
                )
                activity = f"Added certification: {name}."
            db.commit()
            log_activity(g.user["id"], activity)
            flash("Certification saved.", "success")
            return redirect(url_for("main.certifications"))
        except ValueError as exc:
            flash(str(exc), "error")
    items = db.execute(
        "SELECT * FROM certifications WHERE user_id=? ORDER BY id DESC", (g.user["id"],)
    ).fetchall()
    return render_template("certifications.html", certifications=items)


@main.post("/certifications/<int:certificate_id>/delete")
@login_required
def delete_certification(certificate_id):
    certificate = user_owned("certifications", certificate_id)
    db = get_db()
    db.execute("DELETE FROM certifications WHERE id=? AND user_id=?", (certificate_id, g.user["id"]))
    db.commit()
    log_activity(g.user["id"], f"Removed certification: {certificate['name']}.")
    flash("Certification removed.", "success")
    return redirect(url_for("main.certifications"))


@main.route("/analytics")
@login_required
def analytics():
    db = get_db()
    data = dashboard_data(g.user["id"])
    project_count = data["project_count"]
    certificate_count = db.execute(
        "SELECT COUNT(*) AS count FROM certifications WHERE user_id=?", (g.user["id"],)
    ).fetchone()["count"]
    return render_template(
        "analytics.html",
        data=data,
        project_count=project_count,
        certificate_count=certificate_count,
    )


@main.route("/settings", methods=("GET", "POST"))
@login_required
def settings():
    db = get_db()
    if request.method == "POST":
        action = request.form.get("action")
        user = db.execute("SELECT * FROM users WHERE id=?", (g.user["id"],)).fetchone()
        if action == "password":
            current = request.form.get("current_password", "")
            new_password = request.form.get("new_password", "")
            if not check_password_hash(user["password_hash"], current):
                flash("Current password did not match.", "error")
            elif len(new_password) < 8:
                flash("New password must contain at least 8 characters.", "error")
            else:
                db.execute(
                    "UPDATE users SET password_hash=? WHERE id=?",
                    (generate_password_hash(new_password), g.user["id"]),
                )
                db.commit()
                flash("Password changed.", "success")
                return redirect(url_for("main.settings"))
        elif action == "reset_demo":
            if user["email"].lower() != "demo@studentpulse.ai":
                flash("Demo reset is only available from the demo account.", "error")
            else:
                seed_demo(reset=True)
                flash("Sample data restored for the demo account.", "success")
                return redirect(url_for("main.dashboard"))
    is_demo = g.user["email"].lower() == "demo@studentpulse.ai"
    return render_template("settings.html", is_demo=is_demo)

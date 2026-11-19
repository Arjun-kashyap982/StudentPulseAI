from .db import get_db


LEVEL_LABELS = {1: "Beginner", 2: "Intermediate", 3: "Advanced"}


def get_profile(user_id):
    return get_db().execute(
        "SELECT u.name, u.email, p.* FROM users u JOIN profiles p ON p.user_id=u.id WHERE u.id=?",
        (user_id,),
    ).fetchone()


def analyze_readiness(user_id):
    db = get_db()
    profile = get_profile(user_id)
    role = profile["career_goal"] if profile else ""
    requirements = db.execute(
        "SELECT skill_name, target_level, explanation FROM role_skills WHERE role=? ORDER BY skill_name",
        (role,),
    ).fetchall()
    student_skills = db.execute(
        "SELECT name, level, evidence FROM skills WHERE user_id=?", (user_id,)
    ).fetchall()
    by_name = {row["name"].casefold(): row for row in student_skills}
    analysis = []
    for requirement in requirements:
        current = by_name.get(requirement["skill_name"].casefold())
        level = current["level"] if current else 0
        target = requirement["target_level"]
        status = "Strong" if level >= target else "Developing" if level else "Missing"
        priority = "High" if not level and target >= 2 else "Medium"
        analysis.append(
            {
                "name": requirement["skill_name"],
                "target": target,
                "target_label": LEVEL_LABELS[target],
                "level": level,
                "level_label": LEVEL_LABELS.get(level, "Not added"),
                "status": status,
                "priority": priority,
                "explanation": requirement["explanation"],
                "evidence": current["evidence"] if current else "",
                "score": min(level / target, 1) * 100 if target else 0,
            }
        )
    readiness = round(sum(item["score"] for item in analysis) / len(analysis)) if analysis else 0
    return {"role": role, "skills": analysis, "readiness": readiness}


def recommendations(user_id, analysis=None):
    db = get_db()
    analysis = analysis or analyze_readiness(user_id)
    profile = get_profile(user_id)
    completed_tasks = {
        row["skill_name"].casefold(): row["count"]
        for row in db.execute(
            "SELECT skill_name, COUNT(*) AS count FROM tasks "
            "WHERE user_id=? AND completed=1 GROUP BY skill_name",
            (user_id,),
        ).fetchall()
    }
    recommendations_list = []
    for item in sorted(
        (skill for skill in analysis["skills"] if skill["status"] != "Strong"),
        key=lambda skill: (skill["level"] > 0, skill["priority"] != "High", skill["name"]),
    )[:5]:
        completed_for_skill = completed_tasks.get(item["name"].casefold(), 0)
        if completed_for_skill:
            action = "Apply it in a small project"
        elif item["level"] > 0:
            action = "Build a small project" if db.execute(
                "SELECT 1 FROM projects WHERE user_id=? LIMIT 1", (user_id,)
            ).fetchone() else "Try a guided practice exercise"
        else:
            action = "Try a guided practice exercise"
        activity_reason = (
            f"You have completed {completed_for_skill} growth-plan task(s) connected to this skill; "
            if completed_for_skill
            else ""
        )
        recommendations_list.append(
            {
                "title": f"Strengthen {item['name']}",
                "description": (
                    f"{action} that uses {item['name']}, then add your work as evidence. "
                    f"{item['explanation']}"
                ),
                "skill": item["name"],
                "priority": item["priority"],
                "minutes": 90 if item["level"] else 60,
                "reason": (
                    f"{activity_reason}"
                    f"{item['name']} is required for {profile['career_goal']} at "
                    f"{item['target_label']} level; your recorded level is {item['level_label']}."
                ),
                "resource": f"https://www.google.com/search?q={item['name'].replace(' ', '+')}+beginner+tutorial",
                "source": "Rules-based",
            }
        )
    projects = db.execute(
        "SELECT COUNT(*) AS count FROM projects WHERE user_id=?", (user_id,)
    ).fetchone()["count"]
    if projects == 0:
        recommendations_list.append(
            {
                "title": "Create your first portfolio project",
                "description": "Build a focused project connected to your career goal and document what you learned.",
                "skill": "Project evidence",
                "priority": "Medium",
                "minutes": 180,
                "reason": "Projects provide practical evidence that supports your skill profile.",
                "resource": "",
                "source": "Rules-based",
            }
        )
    return recommendations_list[:5]


def dashboard_data(user_id):
    db = get_db()
    profile = get_profile(user_id)
    analysis = analyze_readiness(user_id)
    tasks = db.execute(
        "SELECT * FROM tasks WHERE user_id=? ORDER BY completed, id DESC", (user_id,)
    ).fetchall()
    completed = sum(row["completed"] for row in tasks)
    recent = db.execute(
        "SELECT message, created_at FROM activities WHERE user_id=? ORDER BY id DESC LIMIT 5",
        (user_id,),
    ).fetchall()
    skill_count = db.execute(
        "SELECT COUNT(*) AS count FROM skills WHERE user_id=?", (user_id,)
    ).fetchone()["count"]
    project_count = db.execute(
        "SELECT COUNT(*) AS count FROM projects WHERE user_id=?", (user_id,)
    ).fetchone()["count"]
    return {
        "profile": profile,
        "analysis": analysis,
        "recommendations": recommendations(user_id, analysis),
        "tasks": tasks,
        "completed": completed,
        "pending": len(tasks) - completed,
        "task_progress": round(completed / len(tasks) * 100) if tasks else 0,
        "recent": recent,
        "skill_count": skill_count,
        "project_count": project_count,
    }

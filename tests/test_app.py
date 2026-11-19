import os
import re
import tempfile
import unittest
from unittest.mock import patch

from studentpulse import create_app
from studentpulse.services import analyze_readiness


class StudentPulseTestCase(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.database = os.path.join(self.temp_dir.name, "test.sqlite3")
        self.app = create_app(
            {
                "TESTING": True,
                "SECRET_KEY": "test-secret",
                "DATABASE": self.database,
                "WTF_CSRF_ENABLED": False,
            }
        )
        self.client = self.app.test_client()

    def tearDown(self):
        self.temp_dir.cleanup()

    def login_demo(self):
        return self.client.post(
            "/login",
            data={"email": "demo@studentpulse.ai", "password": "Demo1234!"},
            follow_redirects=True,
        )

    def test_registration_login_and_logout(self):
        response = self.client.post(
            "/register",
            data={"name": "Test Student", "email": "student@example.test", "password": "strong-pass-1"},
            follow_redirects=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Set a career goal", response.data)
        response = self.client.post(
            "/logout", follow_redirects=True
        )
        self.assertIn(b"Log in", response.data)
        response = self.client.post(
            "/login",
            data={"email": "student@example.test", "password": "strong-pass-1"},
            follow_redirects=True,
        )
        self.assertIn(b"Test Student", response.data)

    def test_csrf_protects_form_submissions_outside_testing_mode(self):
        self.app.config["TESTING"] = False
        self.app.config["WTF_CSRF_ENABLED"] = True

        page = self.client.get("/register")
        match = re.search(
            rb'name="csrf_token" value="([^"]+)"', page.data
        )
        self.assertIsNotNone(match)

        response = self.client.post(
            "/register",
            data={
                "name": "Protected Student",
                "email": "protected@example.test",
                "password": "strong-pass-1",
                "csrf_token": match.group(1).decode(),
            },
        )
        self.assertEqual(response.status_code, 302)

        rejected = self.client.post(
            "/register",
            data={
                "name": "Unprotected Student",
                "email": "unprotected@example.test",
                "password": "strong-pass-1",
            },
        )
        self.assertEqual(rejected.status_code, 400)

    def test_production_requires_secret_key(self):
        with patch.dict(os.environ, {"APP_ENV": "production", "SECRET_KEY": ""}):
            with self.assertRaisesRegex(RuntimeError, "Set SECRET_KEY"):
                create_app()

    def test_demo_pages_and_user_data_flows(self):
        self.login_demo()
        for path in (
            "/dashboard",
            "/profile",
            "/career",
            "/skills",
            "/gap-analysis",
            "/growth-plan",
            "/projects",
            "/certifications",
            "/analytics",
            "/settings",
        ):
            with self.subTest(path=path):
                self.assertEqual(self.client.get(path).status_code, 200)

        self.client.post(
            "/skills",
            data={"action": "add", "name": "Testing", "level": "2", "evidence": "Unit tests"},
        )
        duplicate_skill = self.client.post(
            "/skills",
            data={"action": "add", "name": "testing", "level": "1"},
            follow_redirects=True,
        )
        self.assertIn(b"already exists", duplicate_skill.data)
        self.client.post(
            "/profile",
            data={
                "name": "Aarav Updated",
                "college": "Demo College",
                "degree": "MCA",
                "year_semester": "Year 2",
                "programming_languages": "Python, JavaScript",
                "interests": "Python",
                "experience": "Course projects",
            },
        )
        self.assertIn(b"Python, JavaScript", self.client.get("/profile").data)
        self.client.post(
            "/projects",
            data={"name": "Test project", "description": "A demo", "technologies": "Flask"},
        )
        self.client.post(
            "/certifications",
            data={"name": "Test certificate", "issuer": "Test issuer"},
        )
        with self.app.app_context():
            from studentpulse.db import get_db

            project = get_db().execute(
                "SELECT id FROM projects WHERE name='Test project'"
            ).fetchone()
            certificate = get_db().execute(
                "SELECT id FROM certifications WHERE name='Test certificate'"
            ).fetchone()
        self.client.post(
            "/projects",
            data={
                "action": "edit",
                "project_id": str(project["id"]),
                "name": "Updated project",
                "description": "Edited portfolio entry",
                "technologies": "Flask, SQLite",
                "link": "https://example.test/project",
                "completion_date": "2026-01-15",
            },
        )
        self.client.post(
            "/certifications",
            data={
                "action": "edit",
                "certificate_id": str(certificate["id"]),
                "name": "Updated certificate",
                "issuer": "Edited issuer",
                "issue_date": "2026-02-01",
                "link": "https://example.test/certificate",
            },
        )
        before = self.client.get("/growth-plan").data
        self.assertIn(b"Add a task", before)
        self.client.post(
            "/growth-plan",
            data={
                "action": "add",
                "title": "Practice testing",
                "description": "Write focused tests",
                "skill_name": "Testing",
                "priority": "High",
                "estimated_minutes": "30",
            },
        )
        with self.app.app_context():
            from studentpulse.db import get_db

            task = get_db().execute(
                "SELECT id FROM tasks WHERE title='Practice testing'"
            ).fetchone()
        self.client.post(
            "/growth-plan",
            data={"action": "toggle", "task_id": str(task["id"])},
        )
        analytics = self.client.get("/analytics").data
        self.assertIn(b"Growth plan status", analytics)
        self.assertIn(b"2 completed", analytics)
        self.assertIn(b"Updated project", self.client.get("/projects").data)
        self.assertIn(b"Updated certificate", self.client.get("/certifications").data)

    def test_role_change_skill_edit_and_owned_deletion(self):
        self.login_demo()
        self.client.post(
            "/career",
            data={"career_goal": "Python Developer"},
            follow_redirects=True,
        )
        with self.app.app_context():
            from studentpulse.db import get_db

            db = get_db()
            user_id = db.execute(
                "SELECT id FROM users WHERE email='demo@studentpulse.ai'"
            ).fetchone()["id"]
            task_count = db.execute(
                "SELECT COUNT(*) AS count FROM tasks WHERE user_id=? AND role='Python Developer'",
                (user_id,),
            ).fetchone()["count"]
            skill_id = db.execute(
                "SELECT id FROM skills WHERE user_id=? AND name='Python'", (user_id,)
            ).fetchone()["id"]
        self.assertEqual(task_count, 3)
        self.client.post(
            "/skills",
            data={
                "action": "edit",
                "skill_id": str(skill_id),
                "name": "Python",
                "level": "3",
                "evidence": "Updated evidence",
            },
        )
        self.client.post(f"/skills/{skill_id}/delete")
        with self.app.app_context():
            from studentpulse.db import get_db

            self.assertIsNone(
                get_db().execute("SELECT id FROM skills WHERE id=?", (skill_id,)).fetchone()
            )

    def test_external_links_are_validated(self):
        self.login_demo()
        response = self.client.post(
            "/projects",
            data={"name": "Unsafe link project", "link": "javascript:alert(1)"},
            follow_redirects=True,
        )
        self.assertIn(b"valid http(s) project link", response.data)

    def test_visual_assets_render_in_empty_states(self):
        response = self.client.post(
            "/register",
            data={
                "name": "Empty Profile",
                "email": "empty@example.test",
                "password": "strong-pass-1",
            },
            follow_redirects=True,
        )
        self.assertEqual(response.status_code, 200)
        expected_assets = {
            "/dashboard": "empty-skills-robot.svg",
            "/career": "empty-career-path.svg",
            "/gap-analysis": "empty-career-path.svg",
            "/growth-plan": "growth-learning.svg",
            "/skills": "empty-skills-robot.svg",
            "/projects": "empty-project-portfolio.svg",
            "/certifications": "empty-certification-trophy.svg",
        }
        for path, asset in expected_assets.items():
            with self.subTest(path=path):
                page = self.client.get(path)
                self.assertEqual(page.status_code, 200)
                self.assertIn(asset.encode(), page.data)

    def test_readiness_is_deterministic_and_missing_skill_is_zero(self):
        self.login_demo()
        with self.app.app_context():
            from studentpulse.db import get_db

            user_id = get_db().execute(
                "SELECT id FROM users WHERE email='demo@studentpulse.ai'"
            ).fetchone()["id"]
            profile = get_db().execute(
                "SELECT programming_languages FROM profiles WHERE user_id=?", (user_id,)
            ).fetchone()
            analysis = analyze_readiness(user_id)
        self.assertEqual(profile["programming_languages"], "Python, JavaScript")
        self.assertEqual(analysis["role"], "Software Developer")
        self.assertTrue(0 <= analysis["readiness"] <= 100)
        python_skill = next(item for item in analysis["skills"] if item["name"] == "Python")
        self.assertEqual(python_skill["score"], 100)
        missing_skill = next(item for item in analysis["skills"] if item["name"] == "Testing")
        self.assertEqual(missing_skill["score"], 0)
        self.assertEqual(missing_skill["status"], "Missing")

    def test_invalid_registration_and_isolated_accounts(self):
        response = self.client.post(
            "/register",
            data={"name": "Short", "email": "short@example.test", "password": "tiny"},
            follow_redirects=True,
        )
        self.assertIn(b"at least 8 characters", response.data)
        response = self.client.get("/dashboard")
        self.assertEqual(response.status_code, 302)


if __name__ == "__main__":
    unittest.main()

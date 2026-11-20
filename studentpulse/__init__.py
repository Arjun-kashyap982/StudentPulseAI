import os
from pathlib import Path

import click
from flask import Flask
from flask_wtf.csrf import CSRFProtect

from .db import close_db, init_db, seed_demo
from .routes import main


def create_app(test_config=None):
    project_root = Path(__file__).resolve().parent.parent
    app_environment = os.environ.get("APP_ENV", "development").lower()
    secret_key = os.environ.get("SECRET_KEY")
    default_database = (
        "/tmp/studentpulse.sqlite3"
        if os.environ.get("VERCEL")
        else str(Path(project_root / "instance" / "studentpulse.sqlite3"))
    )
    if app_environment == "production" and not secret_key:
        raise RuntimeError("Set SECRET_KEY before starting StudentPulse AI in production.")

    app = Flask(
        __name__,
        instance_relative_config=True,
        template_folder=str(project_root / "templates"),
        static_folder=str(project_root / "static"),
    )
    app.config.from_mapping(
        SECRET_KEY=secret_key or "dev-key-change-before-deployment",
        DATABASE=os.environ.get(
            "DATABASE_PATH", default_database
        ),
        DEBUG=os.environ.get("FLASK_DEBUG", "0") == "1",
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
        SESSION_COOKIE_SECURE=app_environment == "production",
        WTF_CSRF_ENABLED=True,
    )
    if test_config:
        app.config.update(test_config)
    if not os.environ.get("VERCEL"):
        Path(app.instance_path).mkdir(parents=True, exist_ok=True)

    CSRFProtect(app)
    app.register_blueprint(main)
    app.teardown_appcontext(close_db)

    with app.app_context():
        init_db()
        seed_demo()

    @app.cli.command("reset-demo")
    def reset_demo_command():
        """Restore the clearly labeled demo account and its sample data."""
        seed_demo(reset=True)
        click.echo("Demo account restored: demo@studentpulse.ai / Demo1234!")

    return app

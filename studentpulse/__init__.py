import os
from pathlib import Path

import click
from flask import Flask

from .db import close_db, init_db, seed_demo
from .routes import main


def create_app(test_config=None):
    project_root = Path(__file__).resolve().parent.parent
    app = Flask(
        __name__,
        instance_relative_config=True,
        template_folder=str(project_root / "templates"),
        static_folder=str(project_root / "static"),
    )
    app.config.from_mapping(
        SECRET_KEY=os.environ.get("SECRET_KEY", "dev-key-change-before-deployment"),
        DATABASE=os.environ.get(
            "DATABASE_PATH", str(Path(app.instance_path) / "studentpulse.sqlite3")
        ),
        DEBUG=os.environ.get("FLASK_DEBUG", "0") == "1",
    )
    if test_config:
        app.config.update(test_config)
    Path(app.instance_path).mkdir(parents=True, exist_ok=True)

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

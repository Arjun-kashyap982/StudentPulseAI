import os
import sys
from pathlib import Path


project_dir = os.environ.get(
    "STUDENTPULSE_PROJECT_DIR", str(Path(__file__).resolve().parent)
)
if project_dir not in sys.path:
    sys.path.insert(0, project_dir)

os.environ.setdefault("APP_ENV", "production")

from app import app as application

"""App-wide settings. Override the DB location with the LANDAR_DB env var."""
import os
from pathlib import Path

APP_NAME = "LANDAR"
DATA_DIR = Path(os.environ.get("LANDAR_HOME", Path.home() / ".landar"))
DB_PATH = Path(os.environ.get("LANDAR_DB", DATA_DIR / "landar.db"))
MIN_PASSWORD_LEN = 10

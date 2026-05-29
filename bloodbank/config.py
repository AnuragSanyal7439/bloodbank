from pathlib import Path
import os


BASE_DIR = Path(__file__).resolve().parent.parent
INSTANCE_DIR = BASE_DIR / "instance"


def load_dotenv(path: Path | None = None) -> None:
    """Small .env loader so the demo stays dependency-light."""
    env_path = path or BASE_DIR / ".env"
    if not env_path.exists():
        return

    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


load_dotenv()


class Config:
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-only-change-this-secret")
    DATABASE_PATH = Path(os.getenv("DATABASE_PATH", INSTANCE_DIR / "bloodbank.sqlite"))
    DONATION_COOLDOWN_DAYS = int(os.getenv("DONATION_COOLDOWN_DAYS", "90"))
    DEFAULT_LOW_STOCK_THRESHOLD = int(os.getenv("DEFAULT_LOW_STOCK_THRESHOLD", "5"))
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    JSON_SORT_KEYS = False


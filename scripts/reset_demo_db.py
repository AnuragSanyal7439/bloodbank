from pathlib import Path

from bloodbank import create_app
from bloodbank.config import Config


def main() -> None:
    db_path = Path(Config.DATABASE_PATH)
    if db_path.exists():
        db_path.unlink()

    app = create_app()
    with app.app_context():
        print(f"Demo database recreated at {db_path}")


if __name__ == "__main__":
    main()


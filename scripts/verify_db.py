
import sys
from pathlib import Path

# Add the project root to Python's module search path.
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from db.database import engine


def verify_connection():
    """Verify connectivity to the expected PostgreSQL database."""
    try:
        with engine.connect() as connection:
            db_name = connection.execute(
                text("SELECT current_database();")
            ).scalar_one()

            if db_name != "spotify_cms":
                print(
                    f"CRITICAL FAILURE: Connected to [{db_name}], "
                    "not [spotify_cms]."
                )
                sys.exit(1)

            print(
                "SUCCESS: Authenticated and connected to "
                f"PostgreSQL database: [{db_name}]"
            )

    except SQLAlchemyError as exc:
        print(
            "CRITICAL FAILURE: PostgreSQL connection failed. "
            f"Error type: {type(exc).__name__}"
        )
        sys.exit(1)

    finally:
        engine.dispose()


if __name__ == "__main__":
    verify_connection()

import os
from dotenv import load_dotenv

# Initialize environment variables
load_dotenv()

class Settings:
    """Centralized configuration manager for application secrets."""
    PROJECT_NAME: str = "Spotify API Aggregator CMS"

    POSTGRES_URI: str | None = os.getenv("POSTGRES_URI")
    SPOTIFY_CLIENT_ID: str | None = os.getenv("SPOTIFY_CLIENT_ID")
    SPOTIFY_CLIENT_SECRET: str | None = os.getenv("SPOTIFY_CLIENT_SECRET")
    JWT_SECRET_KEY: str | None = os.getenv("JWT_SECRET_KEY")

    def validate_core_secrets(self) -> None:
        """Ensures critical infrastructure variables exist before startup."""
        missing = []
        if not self.POSTGRES_URI:
            missing.append("POSTGRES_URI")
        if not self.SPOTIFY_CLIENT_ID:
            missing.append("SPOTIFY_CLIENT_ID")
        if not self.SPOTIFY_CLIENT_SECRET:
            missing.append("SPOTIFY_CLIENT_SECRET")
        if not self.JWT_SECRET_KEY:
            missing.append("JWT_SECRET_KEY")

        if missing:
            raise ValueError(
                f"CRITICAL STARTUP FAILURE. Missing secrets: {', '.join(missing)}"
            )

settings = Settings()
# settings.validate_core_secrets() # Will activate once real credentials are provisioned

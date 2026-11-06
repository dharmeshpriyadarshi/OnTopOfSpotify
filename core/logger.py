
import logging
import sys
from datetime import datetime
from pathlib import Path

# Resolve the project root independently of the working directory.
PROJECT_ROOT = Path(__file__).resolve().parent.parent
LOGS_DIR = PROJECT_ROOT / "logs"
LOGS_DIR.mkdir(parents=True, exist_ok=True)

# Create a unique log file for each application initialization.
LOG_FILE = datetime.now().strftime(
    "spotify_cms_%Y_%m_%d_%H_%M_%S_%f.log"
)
LOG_FILE_PATH = LOGS_DIR / LOG_FILE

# Configure the application logger.
logger = logging.getLogger("SpotifyCMS")
logger.setLevel(logging.INFO)
logger.propagate = False

# Prevent duplicate handlers during repeated imports or initialization.
if not logger.handlers:
    formatter = logging.Formatter(
        "[%(asctime)s] %(levelname)s | "
        "%(name)s | %(filename)s:%(lineno)d | %(message)s"
    )

    # Persistent file output.
    file_handler = logging.FileHandler(
        LOG_FILE_PATH,
        encoding="utf-8"
    )
    file_handler.setFormatter(formatter)

    # Console output.
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)

    logger.addHandler(file_handler)
    logger.addHandler(console_handler)

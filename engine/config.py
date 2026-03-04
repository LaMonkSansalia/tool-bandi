"""
Centralized configuration — reads from .env via python-dotenv.
Import this module instead of reading os.environ directly.
"""
import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env from engine/ directory
load_dotenv(Path(__file__).parent / ".env")

# Database
DATABASE_URL: str = os.getenv("DATABASE_URL", "postgresql://bandi:bandi@localhost:5432/bandi_db")
REDIS_URL: str = os.getenv("REDIS_URL", "redis://localhost:6379/0")

# LLM
ANTHROPIC_API_KEY: str = os.getenv("ANTHROPIC_API_KEY", "")
CLAUDE_MODEL: str = "claude-sonnet-4-6"

# Telegram
TELEGRAM_BOT_TOKEN: str = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID: str = os.getenv("TELEGRAM_CHAT_ID", "")

# Eligibility thresholds
SCORE_NOTIFICATION_THRESHOLD: int = int(os.getenv("SCORE_NOTIFICATION_THRESHOLD", "60"))
URGENCY_THRESHOLD_DAYS: int = int(os.getenv("URGENCY_THRESHOLD_DAYS", "14"))
ARCHIVE_AFTER_DAYS: int = int(os.getenv("ARCHIVE_AFTER_DAYS", "30"))
DEFAULT_PROJECT_ID: int = int(os.getenv("DEFAULT_PROJECT_ID", "1"))

# Paths
ROOT_DIR = Path(__file__).parent.parent
CONTEXT_DIR = ROOT_DIR / "context"
OUTPUT_DIR = ROOT_DIR / "output" / "bandi"
BANDI_TROVATI_DIR = ROOT_DIR / "bandi_trovati"

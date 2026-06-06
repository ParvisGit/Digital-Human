"""
Centralized logging for Banking Agent. All application logs go to logs/app.log.
"""
import logging
import os
import sys

# BFSI dir is parent of Banking_agent
_bfsi_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
LOG_DIR = os.path.join(_bfsi_dir, "logs")
LOG_FILE = os.path.join(LOG_DIR, "app.log")


def setup_app_logging(level: str | int | None = None):
    """
    Configure logging for the full application. Call at startup from run_grpc.py and streamlit.py.
    Logs go to both console and logs/app.log.
    """
    os.makedirs(LOG_DIR, exist_ok=True)
    log_level = level or os.environ.get("LOG_LEVEL", "INFO")
    if isinstance(log_level, str):
        log_level = getattr(logging, log_level.upper(), logging.INFO)

    fmt = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    formatter = logging.Formatter(fmt)

    # File handler - all app logs
    file_handler = logging.FileHandler(LOG_FILE, encoding="utf-8")
    file_handler.setFormatter(formatter)
    file_handler.setLevel(log_level)

    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    console_handler.setLevel(log_level)

    # Root logger - capture everything
    root = logging.getLogger()
    root.setLevel(log_level)
    # Add handlers (skip if already configured for this process)
    has_file = any(getattr(h, "baseFilename", "").endswith("app.log") for h in root.handlers if hasattr(h, "baseFilename"))
    if not has_file:
        root.addHandler(file_handler)
        root.addHandler(console_handler)

    # App-specific loggers - ensure they propagate to root
    for name in ("banking_grpc", "banking_agent", "langgraph"):
        log = logging.getLogger(name)
        log.setLevel(log_level)
        log.propagate = True

    return LOG_FILE

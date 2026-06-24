"""
Structured JSON logging configuration.

Call setup_logging() once at process startup (in main.py lifespan).
All modules should use logging.getLogger(__name__) — never print().
"""
import logging
import sys


def setup_logging(level: str = "INFO") -> None:
    """Configure root logger with JSON output when pythonjsonlogger is available,
    falling back to a plain timestamped format for local dev without the package."""
    root = logging.getLogger()
    root.setLevel(getattr(logging, level.upper(), logging.INFO))

    if root.handlers:
        return  # Already configured (e.g. pytest captures handlers)

    try:
        from pythonjsonlogger import jsonlogger

        handler = logging.StreamHandler(sys.stdout)
        formatter = jsonlogger.JsonFormatter(
            fmt="%(asctime)s %(name)s %(levelname)s %(message)s",
            datefmt="%Y-%m-%dT%H:%M:%S",
        )
        handler.setFormatter(formatter)
    except ImportError:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(
            logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")
        )

    root.addHandler(handler)

    # Silence noisy third-party loggers in production
    for noisy in ("uvicorn.access", "asyncio", "httpx", "chromadb"):
        logging.getLogger(noisy).setLevel(logging.WARNING)

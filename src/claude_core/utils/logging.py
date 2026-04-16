"""Logging utilities."""

import logging
import sys
from typing import Optional

def setup_logging(level: int = logging.INFO, name: Optional[str] = None) -> logging.Logger:
    """Setup and return a logger."""
    logger = logging.getLogger(name or "claude_core")
    logger.setLevel(level)

    if not logger.handlers:
        handler = logging.StreamHandler(sys.stderr)
        handler.setFormatter(
            logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
        )
        logger.addHandler(handler)

    return logger

logger = setup_logging()
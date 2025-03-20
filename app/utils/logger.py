import os
import sys
from loguru import logger

from app.core.config import config

# Remove default logger
logger.remove()

# Determine log level from config
LOG_LEVEL = config.log_level

# Add console logger
logger.add(
    sys.stderr,
    format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
    level=LOG_LEVEL,
    colorize=True
)

# Create logs directory if it doesn't exist
os.makedirs("logs", exist_ok=True)

# Add file logger
logger.add(
    "logs/snmp_ai.log",
    rotation="10 MB",  # Rotate when file reaches 10MB
    retention="1 month",  # Keep logs for 1 month
    compression="zip",  # Compress rotated logs
    format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}",
    level=LOG_LEVEL
)

# Configure logger for third-party libraries
if not config.debug:
    # Silence logs from third-party libraries in non-debug mode
    logger.configure(handlers=[
        {"sink": sys.stderr, "level": LOG_LEVEL, "filter": lambda record: "app" in record["name"]}
    ])


def get_logger(name: str):
    """Get a logger with the specified name"""
    return logger.bind(name=name)

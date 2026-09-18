import sys
from pathlib import Path
from loguru import logger

from config.settings import settings


def setup_logger():
    logger.remove()
    log_file = Path(settings.log_file)
    log_file.parent.mkdir(parents=True, exist_ok=True)

    logger.add(
        sys.stdout,
        level=settings.log_level,
        format="<level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan> - <level>{message}</level>",
    )

    logger.add(
        str(log_file),
        level=settings.log_level,
        format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function} - {message}",
        rotation="00:00",
        retention="30 days",
    )

    return logger


log = setup_logger()

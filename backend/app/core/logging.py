import logging
import sys
from backend.app.core.config import settings


def setup_logging() -> logging.Logger:
    """
    Configures structured standard logging for the IBVAP backend.
    """
    log_level = logging.DEBUG if settings.DEBUG else logging.INFO
    log_format = (
        "[%(asctime)s] [%(process)d] [%(levelname)s] "
        "[%(name)s:%(lineno)d]: %(message)s"
    )

    logging.basicConfig(
        level=log_level,
        format=log_format,
        handlers=[
            logging.StreamHandler(sys.stdout)
        ]
    )

    logger = logging.getLogger("ibvap")
    logger.setLevel(log_level)
    return logger


logger = setup_logging()

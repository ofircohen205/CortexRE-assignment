import logging
import sys
from loguru import logger

class InterceptHandler(logging.Handler):
    """
    Standard python logging handler that intercepts all logs and dispatches them to Loguru.
    """
    def emit(self, record):
        # Get corresponding Loguru level if it exists
        try:
            level = logger.level(record.levelname).name
        except ValueError:
            level = record.levelno

        # Find caller from where originated the logged message
        frame, depth = logging.currentframe(), 2
        while frame.f_code.co_filename == logging.__file__:
            frame = frame.f_back
            depth += 1

        logger.opt(depth=depth, exception=record.exc_info).log(level, record.getMessage())

def setup_logging(level="INFO"):
    """
    Replaces standard logging with Loguru and intercepts other libraries' logs.
    """
    # Remove all standard handlers
    logging.root.handlers = [InterceptHandler()]
    logging.root.setLevel(level)

    # Intercept logs from specific libraries
    for name in ["uvicorn", "uvicorn.access", "fastapi"]:
        logging_logger = logging.getLogger(name)
        logging_logger.handlers = [InterceptHandler()]
        logging_logger.propagate = False

    # Configure Loguru
    logger.remove()
    logger.add(
        sys.stdout,
        level=level,
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
        backtrace=True,
        diagnose=True,
    )

    logger.info("Logging initialized with Loguru.")

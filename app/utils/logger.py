import logging
import os

# Define the log directory
LOG_DIR = os.path.join(os.path.dirname(__file__), '../logs')
# os.makedirs(LOG_DIR, exist_ok=True)  # Ensure the logs directory exists

logging.basicConfig(level=logging.INFO)
logging.getLogger('tornado').setLevel(logging.ERROR)
logging.getLogger('flask').setLevel(logging.ERROR)

# Formatter for all loggers
_formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')

def get_logger(name, log_file, level=logging.INFO):
    """
    Creates and returns a logger with the specified name, log file, and level.
    """
    logger = logging.getLogger(name)
    logger.setLevel(level)

    # File handler
    file_handler = logging.FileHandler(os.path.join(LOG_DIR, log_file), mode='w')
    file_handler.setFormatter(_formatter)

    # Avoid duplicate handlers
    if not logger.handlers:
        logger.addHandler(file_handler)

    return logger

# Application logger
app_logger = get_logger('app', 'app.log', logging.INFO)

# Proxy logger
proxy_logger = get_logger('proxy', 'proxy.log', logging.INFO)

# Debug logger
debug_logger = get_logger('debug', 'debug.log', logging.DEBUG)
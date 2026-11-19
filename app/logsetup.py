import logging
import os
from logging.handlers import RotatingFileHandler


def get_logger(name: str = "fox_netmap", data_dir: str = "/data") -> logging.Logger:
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger
    logger.setLevel(logging.INFO)
    os.makedirs(data_dir, exist_ok=True)
    file_handler = RotatingFileHandler(
        os.path.join(data_dir, "netmap.log"), maxBytes=1_000_000, backupCount=3, encoding="utf-8"
    )
    file_handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
    logger.addHandler(file_handler)
    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s: %(message)s"))
    logger.addHandler(stream_handler)
    return logger

import logging
import os
import re
from contextlib import suppress
from logging.handlers import RotatingFileHandler


class TokenRedactFilter(logging.Filter):
    """S-12: Embed-Tokens duerfen nicht im Klartext im uvicorn-Accesslog landen."""

    def filter(self, record: logging.LogRecord) -> bool:
        if "token=" in record.getMessage():
            record.msg = re.sub(r"token=[^\s&]+", "token=***", str(record.msg))
            record.args = ()
        return True


def install_access_log_filter() -> None:
    logging.getLogger("uvicorn.access").addFilter(TokenRedactFilter())


def get_logger(name: str = "fox_netmap", data_dir: str = "/data") -> logging.Logger:
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger
    logger.setLevel(logging.INFO)
    os.makedirs(data_dir, exist_ok=True)
    log_path = os.path.join(data_dir, "netmap.log")
    file_handler = RotatingFileHandler(log_path, maxBytes=1_000_000, backupCount=3, encoding="utf-8")
    file_handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
    logger.addHandler(file_handler)
    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s: %(message)s"))
    logger.addHandler(stream_handler)
    with suppress(OSError):
        os.chmod(log_path, 0o600)  # S-17: Log nur fuer den Besitzer
    return logger

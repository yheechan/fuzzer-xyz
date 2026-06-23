import logging
import multiprocessing
from logging.handlers import QueueHandler, QueueListener
from pathlib import Path

log_queue = None
logging_listener = None

debug_log_queue = None
debug_logging_listener = None


def initialize_logging(outdir: Path) -> None:
    global log_queue, logging_listener, debug_log_queue, debug_logging_listener
    log_queue = multiprocessing.Queue()
    file_handler = logging.FileHandler(outdir / "log.txt")
    formatter = logging.Formatter(
        fmt="[%(asctime)s] %(levelname)s in %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    file_handler.setFormatter(formatter)
    logging_listener = QueueListener(log_queue, file_handler)
    logging_listener.start()

    debug_log_queue = multiprocessing.Queue()
    debug_file_handler = logging.FileHandler(outdir / "debug_log.txt")
    debug_formatter = logging.Formatter(
        fmt="[%(asctime)s] %(levelname)s in %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    debug_file_handler.setFormatter(debug_formatter)
    debug_logging_listener = QueueListener(debug_log_queue, debug_file_handler)
    debug_logging_listener.start()
    return


def get_logger(name: str) -> logging.Logger:
    global log_queue
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger

    logger.setLevel(logging.INFO)

    if log_queue is None:
        handler = logging.NullHandler()
    else:
        handler = QueueHandler(log_queue)

    logger.addHandler(handler)
    logger.propagate = False
    return logger


def get_debug_logger(name: str) -> logging.Logger:
    global debug_log_queue
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger

    logger.setLevel(logging.INFO)

    if debug_log_queue is None:
        handler = logging.NullHandler()
    else:
        handler = QueueHandler(debug_log_queue)
    logger.addHandler(handler)
    logger.propagate = False
    return logger


def cleanup_logging() -> None:
    global log_queue, logging_listener, debug_log_queue, debug_logging_listener
    if logging_listener:
        logging_listener.stop()
        logging_listener = None

    if log_queue:
        log_queue.close()
        log_queue.join_thread()
        log_queue = None

    if debug_logging_listener:
        debug_logging_listener.stop()
        debug_logging_listener = None

    if debug_log_queue:
        debug_log_queue.close()
        debug_log_queue.join_thread()
        debug_log_queue = None

    return

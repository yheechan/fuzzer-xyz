import os
import signal

stop = None


def handle_sigint(_signum, _frame):
    if stop is None:
        return

    if stop.is_set():
        return

    stop.set()
    try:
        os.write(1, b"SIGINT received. Exiting gracefully...\n")
    except OSError:
        pass
    return


def init_signal_handler(manager):
    global stop
    stop = manager.Event()
    signal.signal(signal.SIGINT, handle_sigint)


def cleanup_signal_handler():
    global stop
    stop = None
    signal.signal(signal.SIGINT, signal.SIG_DFL)  # Reset to default handler


def request_stop():
    global stop
    if stop is not None:
        stop.set()


def stop_requested():
    if stop is None:
        # try:
        #     os.write(
        #         1,
        #         b"Warning: stop event is not initialized. SIGINT handling may not work properly.\n",
        #     )
        # except OSError:
        #     pass
        return False

    return stop.is_set()

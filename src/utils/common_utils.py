import asyncio
import multiprocessing
import os
import random
import shutil
import signal
import subprocess
import time
import sys
import tarfile

from collections.abc import Iterator
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))
from src.utils.constants import (
    PROJ_ROOT,
)
from src.utils.signals import (
    stop_requested,
)

manager = multiprocessing.Manager()


def get_manager():
    return manager


def check_llvm_tools(fuzzer_tools: list[str] = None) -> bool:
    tools = [
        "opt",
        "clang",
        "clang++",
        "gclang",
        "gclang++",
        "get-bc",
        "llvm-cov",
    ]

    if fuzzer_tools is not None:
        tools.extend(fuzzer_tools)

    for tool in tools:
        if shutil.which(tool) is None:
            print(f"{tool} not found in PATH")
            return False

    return True


def print_elapsed_time(begin_time: float, msg=None):
    cur_time = time.time()
    time_elapsed = cur_time - begin_time
    time_elapsed = time.gmtime(time_elapsed)

    if msg is None:
        time_elapsed_tty = time.strftime("%H hours %M min. %S sec.", time_elapsed)
        print(f"Time elapsed: {time_elapsed_tty}")
    else:
        time_elapsed_tty = time.strftime("%H:%M:%S", time_elapsed)
        print(f"[{time_elapsed_tty}]: {msg}")


def get_func_list(target_prog: Path) -> list[str]:
    function_list_fn = target_prog.with_suffix(".function_list.txt")

    if not function_list_fn.is_file():
        print(f"Function list file {function_list_fn} does not exist")
        return []

    func_list = []
    with open(function_list_fn, "r") as f:
        for line in f:
            func = line.strip()
            if func == "main" or func == "":
                continue
            func_list.append(func)

    return func_list


def remove_file(path: str | Path) -> None:
    try:
        os.remove(path)
    except OSError:
        pass


def run_subprocess(
    cmd: list[str], cwd: Path | None = None, get_output: bool = False
) -> tuple[str, str]:
    out_pipe = subprocess.DEVNULL
    if get_output:
        out_pipe = subprocess.PIPE

    try:
        process = subprocess.Popen(
            cmd,
            cwd=cwd,
            stdout=out_pipe,
            stderr=out_pipe,
            stdin=subprocess.DEVNULL,
            text=True,
            errors="backslashreplace",
            start_new_session=True,
        )

        while True:
            if stop_requested():
                break
            try:
                return process.communicate(timeout=1)
            except subprocess.TimeoutExpired:
                continue

        try:
            process.send_signal(signal.SIGINT)
            return process.communicate(timeout=1.0)
        except (subprocess.TimeoutExpired, ProcessLookupError):
            try:
                os.killpg(os.getpgid(process.pid), signal.SIGKILL)
                return process.communicate()
            except ProcessLookupError:
                return None, None

    except Exception:
        if "process" in locals() and process.poll() is None:
            try:
                os.killpg(os.getpgid(process.pid), signal.SIGKILL)
                process.wait()
            except ProcessLookupError:
                pass
        return None, None


# return True if process finishes within timeout, False if it times out
def run_subprocess_timeout(
    cmd: list[str], timeout: float, cwd: Path | None = None
) -> bool:
    try:
        process = subprocess.Popen(
            cmd,
            cwd=cwd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            stdin=subprocess.DEVNULL,
            start_new_session=True,
        )

        # We will poll the process in small increments to stay responsive to SIGINT
        poll_interval = 1  # seconds
        elapsed_time = 0.0

        while elapsed_time < timeout:
            # Check if SIGINT was captured by the main application
            if stop_requested():
                break

            try:
                # Wait for a short burst
                process.wait(timeout=poll_interval)
                # If wait finishes without throwing an exception, the process exited normally
                return True
            except subprocess.TimeoutExpired:
                elapsed_time += poll_interval

        # If we broke out of the loop, determine if it was a SIGINT or a real timeout
        if stop_requested():
            # Scenario A: Main app received SIGINT.
            # Send SIGINT (or SIGKILL if it ignores it) to the child process.
            try:
                process.send_signal(signal.SIGINT)
                # Give it a brief moment to clean itself up gracefully
                process.wait(timeout=1.0)
            except (subprocess.TimeoutExpired, ProcessLookupError):
                # Force kill if it's stubborn or already gone
                try:
                    os.killpg(os.getpgid(process.pid), signal.SIGKILL)
                    process.wait()
                except ProcessLookupError:
                    pass
            return False

        else:
            # Scenario B: The process actually timed out
            try:
                os.killpg(os.getpgid(process.pid), signal.SIGKILL)
                process.wait()
            except ProcessLookupError:
                pass
            return False

    except Exception:
        # Fallback for unexpected setup errors to prevent orphan processes
        if "process" in locals() and process.poll() is None:
            try:
                os.killpg(os.getpgid(process.pid), signal.SIGKILL)
                process.wait()
            except ProcessLookupError:
                pass
        raise


async def run_subprocess_async(
    program: Path,
    args: list[str],
    cwd: Path | None = None,
    get_output: bool = False,
    env: dict[str, str] | None = None,
) -> tuple:

    out_pipe = asyncio.subprocess.DEVNULL
    if get_output:
        out_pipe = asyncio.subprocess.PIPE

    async def run_process():
        process = await asyncio.create_subprocess_exec(
            program,
            *args,
            stdout=out_pipe,
            stderr=out_pipe,
            stdin=asyncio.subprocess.DEVNULL,
            cwd=cwd,
            start_new_session=True,
            env=env,
        )

        try:
            # 2. Wait for the process to finish naturally within the timeout
            return await process.communicate()

        except asyncio.CancelledError:
            try:
                process.send_signal(signal.SIGINT)

                # 4. Give it a moment to finish gracefully after receiving SIGINT
                await asyncio.wait_for(process.wait(), timeout=5)
            except (asyncio.TimeoutError, asyncio.CancelledError):
                # If it still won't die, force kill it
                # debug_logger.log("Process ignored SIGINT, forcing kill.")
                try:
                    os.killpg(os.getpgid(process.pid), signal.SIGKILL)
                    await process.wait()
                except ProcessLookupError:
                    pass

            raise

    async def wait_for_stop():
        while not stop_requested():
            await asyncio.sleep(5)
        return "STOP_REQUESTED"

    process_task = asyncio.create_task(run_process())
    stop_task = asyncio.create_task(wait_for_stop())
    done: set[asyncio.Task] = set()
    pending: set[asyncio.Task] = {process_task, stop_task}

    try:
        done, pending = await asyncio.wait(
            [process_task, stop_task],
            return_when=asyncio.FIRST_COMPLETED,
        )
    finally:
        for task in pending:
            task.cancel()
        if pending:
            await asyncio.gather(*pending, return_exceptions=True)

    if process_task in done:
        return process_task.result()

    return None, None


async def run_subprocess_async_timeout(
    program: Path,
    args: list[str],
    timeout: float,
    cwd: Path | None = None,
) -> bool:

    async def run_process():
        process = await asyncio.create_subprocess_exec(
            program,
            *args,
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL,
            stdin=asyncio.subprocess.DEVNULL,
            cwd=cwd,
            start_new_session=True,
        )

        try:
            await asyncio.wait_for(process.wait(), timeout=timeout)

        except asyncio.TimeoutError:
            try:
                if process.returncode is None:
                    os.killpg(os.getpgid(process.pid), signal.SIGKILL)
                    await process.wait()
            except ProcessLookupError:
                pass

            return False

        except asyncio.CancelledError:
            try:
                process.send_signal(signal.SIGINT)

                # Give it a moment to finish gracefully after receiving SIGINT
                await asyncio.wait_for(process.wait(), timeout=5)
            except (asyncio.TimeoutError, asyncio.CancelledError):
                # If it still won't die, force kill it
                try:
                    os.killpg(os.getpgid(process.pid), signal.SIGKILL)
                    await process.wait()
                except ProcessLookupError:
                    pass

            raise

        return True

    async def wait_for_stop():
        while not stop_requested():
            await asyncio.sleep(5)
        return "STOP_REQUESTED"

    process_task = asyncio.create_task(run_process())
    stop_task = asyncio.create_task(wait_for_stop())
    done: set[asyncio.Task] = set()
    pending: set[asyncio.Task] = {process_task, stop_task}

    try:
        done, pending = await asyncio.wait(
            [process_task, stop_task],
            return_when=asyncio.FIRST_COMPLETED,
        )
    finally:
        for task in pending:
            task.cancel()
        if pending:
            await asyncio.gather(*pending, return_exceptions=True)

    if process_task in done:
        return process_task.result()

    return False


def buffered_random_iter(path: Path, buffer_size: int = 1000) -> Iterator[Path]:
    iterator = path.iterdir()
    buffer = []

    for _ in range(buffer_size):
        try:
            buffer.append(next(iterator))
        except StopIteration:
            break

    random.shuffle(buffer)

    for item in iterator:
        idx = random.randint(0, len(buffer) - 1)
        yield buffer[idx]
        buffer[idx] = item

    random.shuffle(buffer)
    while buffer:
        yield buffer.pop()


def read_bbcov_file(cov_file: Path) -> dict[str, set[int]]:
    cur_func = ""
    bb_cov = dict()
    with open(cov_file, "r") as f:
        for line in f:
            line = line.strip().split(" ")
            if len(line) != 3:
                continue

            if line[0] == "F":
                if line[2] != "1":
                    continue
                cur_func = line[1]
                bb_cov[cur_func] = set()
                continue

            elif line[0] == "B":
                if line[2] != "1":
                    continue

                try:
                    BB_index = int(line[1])
                except ValueError:
                    continue

                bb_cov[cur_func].add(BB_index)

    return bb_cov

def unpack_targz(targz_path: Path, output_dir: Path) -> bool:
    """
    Unpack a .tar.gz file to the specified output directory.

    Args:
        targz_path (Path): The path to the .tar.gz file.
        output_dir (Path): The directory where the contents will be extracted.

    Returns:
        bool: True if extraction was successful, False otherwise.
    """
    if not targz_path.is_file():
        print(f"Error: {targz_path} is not a valid file.")
        return False

    try:
        with tarfile.open(targz_path, "r:gz") as tar:
            tar.extractall(path=output_dir)
        return True
    except Exception as e:
        print(f"Error extracting {targz_path}: {e}")
        return False

def pip_install_requirements(server_address: str) -> bool:
    """
    Install the required Python packages on the server using pip.

    Args:
        server_address (str): The address of the server.

    Returns:
        bool: True if the installation was successful, False otherwise.
    """
    # Check if if .venv directory exists on the server
    cmd = f"ssh {server_address} 'ls {PROJ_ROOT}/.venv'"
    result = subprocess.run(
        cmd,
        shell=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE
    )
    result_str = result.stderr.decode().strip()
    on_server = False if "No such file or directory" in result_str else True

    if not on_server:
        cmd = f"ssh {server_address} 'cd {PROJ_ROOT} && python3 -m venv .venv'"
        result = subprocess.run(
            cmd,
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        print(f"[VENV] Created virtual environment on server {server_address}.")

    cmd = f"ssh {server_address} 'cd {PROJ_ROOT} && source .venv/bin/activate && pip install -r requirements.txt'"
    result = subprocess.run(
        cmd,
        shell=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
    )
    
    return True
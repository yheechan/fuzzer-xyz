import sys
import argparse
import subprocess
import logging
import threading

from collections import deque
from datetime import datetime
from dataclasses import dataclass
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed


ROOT_DIR = Path(__file__).resolve().parent.parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from src.utils.constants import (
    BASELINE_FUZZERS,
    TARGET_SUBJECTS,
    RESEARCH_ROOT
)
from src.utils.configs import (
    SERVER_ADDRESS_LIST
)
from src.utils.common_utils import (
    pip_install_requirements
)
from src.utils.log import (
    setup_task_logger
)
from src.fuzzer.fuzzer_factory import FuzzerFactory
from src.fuzzer.fuzzer import Fuzzer

@dataclass
class Task:
    output_dirn: str
    fuzzer_name: str
    fuzzer: Fuzzer
    targz_fp: Path      # absolute path to <fuzz_id>.tar.gz
    window_size: int = 10  # Default window size is 10 minutes

    def __str__(self) -> str:
        return f"{self.fuzzer.target_program}${self.fuzzer}${self.fuzzer.experiment_name}${self.fuzzer.fuzz_id}"

@dataclass
class ParsedArgv:
    output_dirp: Path
    output_dirn: str
    fuzzer: str
    experiment_name: str
    parallel: int = 8 # Default number of parallel tasks per server
    window_size: int = 10  # Default window size is 10 minutes

def run_cmd(cmd: str) -> subprocess.CompletedProcess:
    """Run a shell command, capturing stdout/stderr as text."""
    return subprocess.run(
        cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
    )

def remote_path_exists(server: str, path: Path, is_dir: bool = False) -> bool:
    """Return True if `path` exists on `server` (dir test if is_dir, else any)."""
    flag = "-d" if is_dir else "-e"
    return run_cmd(f"ssh {server} 'test {flag} {path}'").returncode == 0

def parse_argv() -> ParsedArgv:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "-o",
        "--output-dir",
        type=str,
        required=True,
        help="Directory holding fuzzing and coverage results of all target programs.",
        metavar="OUTPUT_DIR"
    )
    parser.add_argument(
        "-f",
        "--fuzzer",
        type=str,
        required=True,
        help="Fuzzer that generated the inputs to measure coverage.",
        choices=list(BASELINE_FUZZERS.keys())
    )
    parser.add_argument(
        "-e",
        "--experiment-name",
        type=str,
        required=True,
        help="Name of the experiment to get coverage data for.",
        metavar="EXPERIMENT_NAME"
    )
    parser.add_argument(
        "-p",
        "--parallel",
        type=int,
        default=8,
        required=False,
        help="Number of parallel tasks to run on each server. Default is 8.",
        metavar="PARALLEL_TASKS"
    )
    parser.add_argument(
        "-w",
        "--window-size",
        type=int,
        required=False,
        help="Window size in minutes for coverage data aggregation.",
        metavar="WINDOW_SIZE"
    )
    argv = parser.parse_args()
    output_dirn = argv.output_dir
    argv.output_dir = Path(argv.output_dir).absolute()

    return ParsedArgv(
        output_dirp=argv.output_dir,
        output_dirn=output_dirn,
        fuzzer=argv.fuzzer,
        experiment_name=argv.experiment_name,
        parallel=argv.parallel,
        window_size=argv.window_size
    )

def install_requirements_on_servers(logger: logging.Logger = None):
    with ThreadPoolExecutor(max_workers=5) as executor:
        futures = []
        for server_address in SERVER_ADDRESS_LIST:
            futures.append(
                executor.submit(
                    pip_install_requirements,
                    server_address=server_address,
                )
            )
        for future in as_completed(futures):
            try:
                future.result()
            except Exception as e:
                if logger:
                    logger.error(f"Error during pip install on server: {e}")
    
def form_tasks(parsed_argv: ParsedArgv) -> tuple[list[Task], dict[str, int]]:
    tasks: list[Task] = []
    target2cnt = {}

    for target_dir in sorted(parsed_argv.output_dirp.iterdir()):
        if not target_dir.is_dir():
            continue

        target = target_dir.name
        if target not in TARGET_SUBJECTS:
            logging.warning(f"Skipping {target}: not in TARGET_SUBJECTS.")
            continue

        baseline_fuzz_dir = target_dir / "baseline_fuzzing"
        if not baseline_fuzz_dir.is_dir():
            continue

        fuzzer_class_name = BASELINE_FUZZERS[parsed_argv.fuzzer]
        fuzzer_dirp = baseline_fuzz_dir / fuzzer_class_name
        if not fuzzer_dirp.is_dir():
            continue

        experiment_dir = fuzzer_dirp / parsed_argv.experiment_name
        if not experiment_dir.is_dir():
            continue

        # if not experiment_dir.is_dir():
        #     raise RuntimeError(
        #         f"Expected {experiment_dir} to exist ({fuzzer_class_name}/{parsed_argv.experiment_name})"
        #     )

        coverage_dir = experiment_dir / "coverage"
        if not coverage_dir.is_dir():
            coverage_dir.mkdir(parents=True, exist_ok=True)
        
        fuzz_outputs_dirp = experiment_dir / "fuzz_outputs"
        if not fuzz_outputs_dirp.is_dir():
            raise RuntimeError(
                f"Expected {fuzz_outputs_dirp} to exist ({fuzzer_class_name}/{parsed_argv.experiment_name})"
            )

        for targz_fp in sorted(fuzz_outputs_dirp.glob("*.tar.gz")):
            # print(f"[INFO] Found trial tarball: {targz_fp}")
            fuzz_id = targz_fp.name[: -len(".tar.gz")]

            gcov_csv = coverage_dir / f"{target}.{fuzz_id}.gcov.csv"
            bbcov_csv = coverage_dir / f"{target}.{fuzz_id}.bbcov.csv"
            if gcov_csv.exists() and bbcov_csv.exists():
                # logging.info(f"[SKIP] {target}/{fuzz_id}: coverage CSVs already exist.")
                continue

            fuzzer: Fuzzer = FuzzerFactory.create_fuzzer(
                output_dir=target_dir,
                target_program=target,
                fuzzer_name=parsed_argv.fuzzer,
                experiment_name=parsed_argv.experiment_name,
                fuzz_id=fuzz_id
            )

            output_dirn = "/".join(parsed_argv.output_dirn.split("/") + [target])

            target2cnt[target] = target2cnt.get(target, 0) + 1
            tasks.append(Task(
                output_dirn=output_dirn,
                fuzzer_name=parsed_argv.fuzzer,
                fuzzer=fuzzer,
                targz_fp=targz_fp,
                window_size=parsed_argv.window_size
            ))
    
    return tasks, target2cnt

def run_task_on_server(task: Task, server: str, logger: logging.Logger) -> bool:
    """Send (if needed), extract coverage on the server, and fetch back the CSVs."""

    tag = f"[{server}][{task}]"
    start_time = datetime.now()
    logger.info(f"{tag} Starting coverage extraction.")




    # 1. Ensure the build/drivers are present on the server (sent once per target
    #    per server). The baseline binary's presence is the proxy used to decide.
    if not task.fuzzer.coverage_targets_on_server(server):
        logger.info(f"[SEND] {tag} Drivers missing on server; SCP build artifacts...")
        success = task.fuzzer.send_fuzz_targets_to_server(server)
        if not success:
            logger.error(f"[SEND-ERROR] {tag} Failed to send coverage targets to server {server}.")
            sys.exit(1)

        if task.fuzzer.coverage_targets_on_server(server):
            logger.info(f"[SEND] {tag} Successfully sent coverage targets to server {server}.")
        else:
            logger.error(f"[SEND-ERROR] {tag} Coverage targets not found on server {server}.")
            sys.exit(1)
    else:
        logger.info(f"[SKIP-SEND] {tag} Coverage targets already present on server {server}.")




    # 2. Ensure the fuzzing trial is present on the server. Send + untar if not.
    if not remote_path_exists(server, task.targz_fp, is_dir=False):
        logger.info(f"[SEND] {tag} Trial missing on server; sending {task.targz_fp.name}...")
        tar_dirp = task.targz_fp.parent
        run_cmd(f"ssh {server} 'mkdir -p {tar_dirp}'")

        res = run_cmd(f"scp -q {task.targz_fp} {server}:{tar_dirp}/")
        if res.returncode != 0:
            logger.error(f"{tag} Failed to send tarball: {res.stderr.strip()}")
            return False
        
        if remote_path_exists(server, task.targz_fp, is_dir=False):
            logger.info(f"[SEND] {tag} Successfully sent trial to server.")
        else:
            logger.error(f"[SEND-ERROR] {tag} Trial not found on server after sending.")
            sys.exit(1)
    else:
        logger.info(f"[SKIP-SEND] {tag} Trial already present on server.")






    # 3. Run coverage extraction on the server.
    logger.info(f"[BEGIN] {tag} Running run_coverage_extraction.py...")
    extract_cmd = (
        f"ssh {server} 'cd {RESEARCH_ROOT} && source fuzzer-xyz/.venv/bin/activate && "
        f"python3 fuzzer-xyz/src/scripts/get_cov.py "
        f"-o {task.output_dirn} -t {task.fuzzer.target_program} -f {task.fuzzer_name} -e {task.fuzzer.experiment_name} -fid {task.fuzzer.fuzz_id} -w {task.window_size}'"
    )
    res = run_cmd(extract_cmd)
    if res.returncode != 0:
        logger.error(f"{tag} Coverage extraction failed: {res.stderr.strip()}")
        return False




    # 4. Bring back only the two coverage CSVs.
    coverage_dir = task.fuzzer.output_dir / "baseline_fuzzing" / task.fuzzer.__class__.__name__ / task.fuzzer.experiment_name / "coverage"
    logs_dir = task.fuzzer.output_dir / "baseline_fuzzing" / task.fuzzer.__class__.__name__ / task.fuzzer.experiment_name / "logs"

    coverage_dir.mkdir(parents=True, exist_ok=True)
    for suffix in ("gcov.csv", "bbcov.csv"):
        remote_csv = coverage_dir / f"{task.fuzzer.target_program}.{task.fuzzer.fuzz_id}.{suffix}"
        res = run_cmd(f"scp -q {server}:{remote_csv} {coverage_dir}/")
        if res.returncode != 0:
            logger.error(f"{tag} Failed to fetch {remote_csv.name}: {res.stderr.strip()}")
            return False
    
    logs_dir.mkdir(parents=True, exist_ok=True)
    for suffix in ("bbcov.log", "gcov.log", "coverage.log"):
        remote_log = logs_dir / f"{task.fuzzer.fuzz_id}.{suffix}"
        res = run_cmd(f"scp -q {server}:{remote_log} {logs_dir}/")
        if res.returncode != 0:
            logger.error(f"{tag} Failed to fetch log {remote_log.name}: {res.stderr.strip()}")
            return False

    elapsed = (datetime.now() - start_time).total_seconds() / 60
    logger.info(f"{tag} Done in {elapsed:.1f} min. CSVs in {coverage_dir}.")


    return True

def schedule(tasks: list[Task], per_server: int, logger: logging.Logger) -> list[tuple[Task, str, bool]]:
    cond = threading.Condition()
    pending = deque(tasks)
    running_targets: dict[str, set[str]] = {s: set() for s in SERVER_ADDRESS_LIST}
    results: list[tuple[Task, str, bool]] = []

    def worker(server: str):
        while True:
            with cond:
                while True:
                    if not pending:
                        return
                    # first task whose target isn't already running on this server
                    pick = next(
                        (
                            i
                            for i, t in enumerate(pending)
                            if t.fuzzer.target_program not in running_targets[server]
                        ),
                        None,
                    )
                    if pick is not None:
                        task = pending[pick]
                        del pending[pick]
                        running_targets[server].add(task.fuzzer.target_program)
                        cond.notify_all()  # pending shrank; wake waiters
                        break
                    # pending non-empty but nothing eligible here right now; wait
                    cond.wait()

            ok = False
            try:
                ok = run_task_on_server(task, server, logger)
            except Exception:
                logger.exception(f"[{server}][{task}] Unexpected error.")
            finally:
                with cond:
                    running_targets[server].discard(task.fuzzer.target_program)
                    results.append((task, server, ok))
                    cond.notify_all()  # freed a slot/target; wake waiters

    threads = []
    for server in SERVER_ADDRESS_LIST:
        for _ in range(per_server):
            th = threading.Thread(target=worker, args=(server,), name=server, daemon=True)
            th.start()
            threads.append(th)
    for th in threads:
        th.join()

    return results


def main():
    parsed_argv = parse_argv()

    logger = setup_task_logger(
        name="get_cov",
        stdout=True
    )



    # 1. Install required packages for all servers (multiprocess max 5)
    logger.info("Installing required packages on all servers...")
    install_requirements_on_servers(logger)
    logger.info("Package installation completed on all servers.")



    # 2. Form the task list (skip trials whose coverage CSVs already exist)
    logger.info("Forming task list...")
    tasks, target2cnt = form_tasks(parsed_argv)
    if not tasks:
        logger.info("No tasks to process. Exiting.")
        return
    logger.info(f"Total tasks formed: {len(tasks)}")
    for target, count in target2cnt.items():
        logger.info(f"  - {target}: {count} task(s)")
    logger.info(f"Distributing tasks across servers: {len(SERVER_ADDRESS_LIST)} servers available. {parsed_argv.parallel} tasks per server.")



    # 2-4. Schedule, send/extract, and fetch results.
    start_time = datetime.now()
    results = schedule(tasks, parsed_argv.parallel, logger)
    elapsed = (datetime.now() - start_time).total_seconds() / 3600

    succeeded = [t for t, _, ok in results if ok]
    failed = [(t, s) for t, s, ok in results if not ok]

    logger.info(f"[DONE] {len(succeeded)}/{len(results)} tasks succeeded in {elapsed:.2f} h.")
    if failed:
        logger.warning(f"{len(failed)} task(s) failed:")
        for task, server in failed:
            logger.warning(f"  - {task} on {server}")
    


if __name__ == "__main__":
    main()

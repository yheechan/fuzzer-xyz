import argparse
import subprocess
import sys

from dataclasses import dataclass
from pathlib import Path
from datetime import datetime

ROOT_DIR = Path(__file__).resolve().parent.parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from src.fuzzer.fuzzer_factory import FuzzerFactory
from src.fuzzer.fuzzer import Fuzzer
from src.utils.constants import (
    PROJ_ROOT,
    TARGET_SUBJECTS,
    BASELINE_FUZZERS,
    RESEARCH_ROOT
)
from src.utils.common_utils import (
    pip_install_requirements
)

@dataclass
class ParsedArgv:
    output_dir: Path
    target_program: str
    fuzzer: str
    server: str
    experiment_name: str
    output_dir_str: str
    NUM_FUZZERS: int = 4
    duration: str = "24h"  # Default duration is 24 hours

def parse_argv() -> ParsedArgv:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "-o",
        "--output-dir",
        type=str,
        required=True,
        help="Directory to store the compiled driver files",
        metavar="OUTPUT_DIR",
    )
    parser.add_argument(
        "-t",
        "--target-program",
        type=str,
        required=True,
        help="Name of the target program to compile",
        choices=TARGET_SUBJECTS,
        metavar="TARGET_PROGRAM",
    )
    parser.add_argument(
        "-f",
        "--fuzzer",
        type=str,
        required=True,
        help="Fuzzer to prepare compilation targets for. If not specified.",
        choices=list(BASELINE_FUZZERS.keys()),
        metavar="FUZZER",
    )
    parser.add_argument(
        "-s",
        "--server",
        type=str,
        required=True,
        help="Server address for fuzzing",
        metavar="SERVER_ADDRESS",
    )
    parser.add_argument(
        "-e",
        "--experiment-name",
        type=str,
        required=True,
        help="Name of the experiment for organizing output directories.",
        metavar="EXPERIMENT_NAME",
    )
    parser.add_argument(
        "-p",
        "--parallel",
        type=int,
        required=False,
        default=4,
        help="Number of parallel fuzzing processes to run. Default is 4.",
        metavar="NUM_FUZZERS",
    )
    parser.add_argument(
        "-d",
        "--duration",
        type=str,
        required=False,
        default="24h",
        help="Duration of the fuzzing experiment. Default is 24h. (e.g., '24h', '30m', '10s').",
        metavar="DURATION",
    )

    argv = parser.parse_args()
    output_dir_str = argv.output_dir
    argv.output_dir = Path(argv.output_dir).absolute()

    if argv.duration[-1] not in ['h', 'm', 's']:
        print("Invalid duration format. Use 'h' for hours, 'm' for minutes, or 's' for seconds.")
        sys.exit(1)
    

    return ParsedArgv(
        output_dir=argv.output_dir,
        target_program=argv.target_program,
        fuzzer=argv.fuzzer,
        server=argv.server,
        experiment_name=argv.experiment_name,
        output_dir_str=output_dir_str,
        NUM_FUZZERS=argv.parallel,
        duration=argv.duration,
    )

def run_fuzz_on_server(parsed_argv, fuzz_id) -> bool:
    """
    Run the fuzzing experiment on the server.

    Args:
        server_address (str): The address of the server.
        fuzzer (Fuzzer): The fuzzer instance to run.
        fuzz_id (str): Unique identifier for the fuzzing run.

    Returns:
        bool: True if the fuzzing experiment was started successfully, False otherwise.
    """
    server_address = parsed_argv.server
    duration = parsed_argv.duration
    output_dir_str = parsed_argv.output_dir_str
    target_program = parsed_argv.target_program
    fuzzer_name = parsed_argv.fuzzer
    experiment_name = parsed_argv.experiment_name
    NUM_FUZZERS = parsed_argv.NUM_FUZZERS
    fuzz_id = fuzz_id

    cmd = f"ssh {server_address} 'cd {RESEARCH_ROOT} && source {PROJ_ROOT}/.venv/bin/activate && timeout --signal=2 {duration} python3 {PROJ_ROOT}/src/scripts/fuzz.py -o {output_dir_str} -t {target_program} -f {fuzzer_name} -e {experiment_name} -p {NUM_FUZZERS} -fid {fuzz_id}'"

    start_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[TIME] Fuzz start time: {start_time}")
    print(f"\t FUZZ ID: {fuzz_id}")

    result = subprocess.run(
        cmd,
        shell=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
    )
    
    # if result.returncode != 0:
    #     print(f"[FUZZ-ERROR] Failed to fuzz on server {server_address}. Error: {result.stderr}")
    #     return False

    end_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[TIME] Fuzz end time: {end_time}")

    # Calculate elapsed time
    start_dt = datetime.strptime(start_time, "%Y-%m-%d %H:%M:%S")
    end_dt = datetime.strptime(end_time, "%Y-%m-%d %H:%M:%S")
    elapsed_time = (end_dt - start_dt).total_seconds() / 3600  # Convert seconds to hours
    print(f"[TIME] Total elapsed time: {elapsed_time} hours")

    print(f"[FUZZ-SUCCESS] Fuzzing experiment started on server {server_address} for fuzzer {fuzzer_name}.")

    return True

def main():
    parsed_argv = parse_argv()

    fuzzer: Fuzzer = FuzzerFactory.create_fuzzer(
        output_dir=parsed_argv.output_dir,
        target_program=parsed_argv.target_program,
        fuzzer_name=parsed_argv.fuzzer,
        experiment_name=parsed_argv.experiment_name
    )

    success = fuzzer.check_fuzz_targets()
    if not success:
        print(f"Fuzz target check failed for {parsed_argv.target_program} with fuzzer {parsed_argv.fuzzer}.")
        sys.exit(1)

    # 1. Send fuzz targets to the server if they are not already present
    if not fuzzer.targets_on_server(parsed_argv.server):
        print(f"[SEND] SCP fuzzing targets to server {parsed_argv.server} for fuzzer {parsed_argv.fuzzer}.")

        success = fuzzer.send_fuzz_targets_to_server(parsed_argv.server)
        if not success:
            print(f"[SEND-ERROR] Failed to send fuzzing targets to server {parsed_argv.server} for fuzzer {parsed_argv.fuzzer}.")
            sys.exit(1)

        if fuzzer.targets_on_server(parsed_argv.server):
            print(f"[SEND] Successfully sent fuzzing targets to server {parsed_argv.server} for fuzzer {parsed_argv.fuzzer}.")
        else:
            print(f"[SEND-ERROR] Fuzzing targets not found on server {parsed_argv.server} after sending for fuzzer {parsed_argv.fuzzer}.")
            sys.exit(1)
    else:
        print(f"[SKIP-SEND] Fuzzing targets already present on server {parsed_argv.server} for fuzzer {parsed_argv.fuzzer}.")

    # 2. Install required Python packages on the server
    success = pip_install_requirements(parsed_argv.server)
    if not success:
        print(f"[PIP-ERROR] Failed to install required Python packages on server {parsed_argv.server}.")
        sys.exit(1)
    else:
        print(f"[PIP] Successfully installed required Python packages on server {parsed_argv.server}.")
    
    # 3. Run the fuzzing experiment on the server
    now = datetime.now()
    fuzz_id = now.strftime("%m%d_%H%M%S")

    success = run_fuzz_on_server(parsed_argv, fuzz_id)
    if not success:
        print(f"[FUZZ-ERROR] Fuzzing experiment failed on server {parsed_argv.server}.")
        sys.exit(1)

    # 4. Retrieve fuzz output and logs
    success = fuzzer.retrieve_fuzz_results_from_server(parsed_argv.server, fuzz_id)
    if not success:
        print(f"[RETRIEVE-ERROR] Failed to retrieve fuzzing results from server {parsed_argv.server}.")
        sys.exit(1)
    else:
        print(f"[RETRIEVE] Successfully retrieved fuzzing results from server {parsed_argv.server}.")
    
    print(f"[GRACEFUL-EXIT] Fuzzing experiment completed successfully on server {parsed_argv.server} with fuzz ID {fuzz_id}. Exiting gracefully.")

if __name__ == "__main__":
    main()

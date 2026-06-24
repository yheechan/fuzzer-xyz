import argparse
import sys

from dataclasses import dataclass
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from src.fuzzer.fuzzer_factory import FuzzerFactory
from src.fuzzer.fuzzer import Fuzzer
from src.utils.constants import (
    TARGET_SUBJECTS,
    BASELINE_FUZZERS
)

@dataclass
class ParsedArgv:
    output_dir: Path
    target_program: str
    fuzzer: str
    server: str
    experiment_name: str
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
        choices=BASELINE_FUZZERS,
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
        NUM_FUZZERS=argv.parallel,
        duration=argv.duration
    )

def main():
    parsed_args = parse_argv()

    fuzzer: Fuzzer = FuzzerFactory.create_fuzzer(
        output_dir=parsed_args.output_dir,
        target_program=parsed_args.target_program,
        experiment_name=parsed_args.experiment_name
    )

    success = fuzzer.check_fuzz_targets()
    if not success:
        print(f"Fuzz target check failed for {parsed_args.target_program} with fuzzer {parsed_args.fuzzer}.")
        sys.exit(1)

    # TODO:
    # Set FUZZ_ID to the current timestamp
    # Send
    # Execute
    # Retrieve

    

if __name__ == "__main__":
    main()

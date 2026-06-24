import argparse
import sys

from pathlib import Path
from dataclasses import dataclass
from datetime import datetime

ROOT_DIR = Path(__file__).resolve().parent.parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from src.utils.constants import (
    TARGET_SUBJECTS,
    BASELINE_FUZZERS
)

from src.fuzzer.fuzzer_factory import FuzzerFactory
from src.fuzzer.fuzzer import Fuzzer

@dataclass
class ParsedArgv:
    output_dir: Path
    target_program: str
    fuzzer: str
    experiment_name: str
    fuzz_id: str

def parse_argv() -> ParsedArgv:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "-o",
        "--output-dir",
        type=str,
        required=True,
        help="Directory to store the compiled bitcode files",
        metavar="OUTPUT_DIR",
    )
    parser.add_argument(
        "-t",
        "--target-program",
        type=str,
        required=True,
        help="Name of the target program to compile",
        metavar="TARGET_PROGRAM",
        choices=TARGET_SUBJECTS
    )
    parser.add_argument(
        "-f",
        "--fuzzer",
        type=str,
        required=True,
        help="Fuzzer to prepare compilation targets for. If not specified.",
        metavar="FUZZER",
        choices=BASELINE_FUZZERS
    )
    parser.add_argument(
        "-fid",
        "--fuzz-id",
        required=False,
        default=None,
        help="Fuzzing id to distinguish different fuzzing runs. If not specified, it will be set to the current timestamp.",
        metavar="FUZZ_ID"
    )
    parser.add_argument(
        "-e",
        "--experiment-name",
        type=str,
        required=True,
        help="Name of the experiment to run. This will be used to create a subdirectory under the output directory to store fuzzing results.",
        metavar="EXPERIMENT_NAME"
    )
    
    argv = parser.parse_args()
    if argv.fuzz_id is None:
        now = datetime.now()
        argv.fuzz_id = now.strftime("%m%d_%H%M%S")

    argv.output_dir = Path(argv.output_dir).absolute()
    
    return ParsedArgv(
        output_dir=argv.output_dir,
        target_program=argv.target_program,
        fuzzer=argv.fuzzer,
        experiment_name=argv.experiment_name,
        fuzz_id=argv.fuzz_id
    )

def main():
    parsed_args = parse_argv()
    print(f"Parsed arguments: {parsed_args}")

    fuzzer: Fuzzer = FuzzerFactory.create_fuzzer(
        output_dir=parsed_args.output_dir,
        target_program=parsed_args.target_program,
        fuzzer_name=parsed_args.fuzzer,
        experiment_name=parsed_args.experiment_name,
        fuzz_id=parsed_args.fuzz_id
    )

    success = fuzzer.init_fuzz_output_dir()
    if not success:
        print("Failed to initialize fuzz output directory.")
        sys.exit(1)

    success = fuzzer.init_fuzz_logger()
    if not success:
        print("Failed to initialize fuzz logger.")
        sys.exit(1)

    success = fuzzer.set_general_requirements()
    if not success:
        print("Failed to set general requirements.")
        sys.exit(1)

    success = fuzzer.check_fuzz_targets()
    if not success:
        print("Failed to check fuzz targets.")
        sys.exit(1)
    
    fuzzer.fuzz()

if __name__ == "__main__":
    main()

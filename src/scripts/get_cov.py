import argparse
import sys

from dataclasses import dataclass
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor

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
    no_cleanup: bool
    window_size: int = 10  # Default window size is 10 minutes

def parse_argv() -> ParsedArgv:
    parser = argparse.ArgumentParser(description="Get coverage data for a target program.")
    parser.add_argument(
        "-o",
        "--output-dir",
        type=Path,
        required=True,
        help="Directory to store the coverage data.",
        metavar="OUTPUT_DIR"
    )
    parser.add_argument(
        "-t",
        "--target-program",
        type=str,
        required=True,
        help="The target program to analyze for coverage.",
        choices=TARGET_SUBJECTS,
        metavar="TARGET_PROGRAM",
    )
    parser.add_argument(
        "-f",
        "--fuzzer",
        type=str,
        required=True,
        help="The fuzzer used to generate the coverage data.",
        choices=BASELINE_FUZZERS,
        metavar="FUZZER",
    )
    parser.add_argument(
        "-e",
        "--experiment-name",
        type=str,
        required=True,
        help="The name of the experiment for which coverage data is being collected.",
        metavar="EXPERIMENT_NAME",
    )
    parser.add_argument(
        "-fid",
        "--fuzz-id",
        type=str,
        required=True,
        help="The fuzzing ID to associate with the coverage data.",
        metavar="FUZZ_ID",
    )
    parser.add_argument(
        "-w",
        "--window-size",
        type=int,
        required=False,
        default=10,
        help="The window size for coverage analysis. Default is 10 (in minutes).",
        metavar="WINDOW_SIZE"
    )
    parser.add_argument(
        "-x",
        "--no-cleanup",
        action="store_true",
        default=False,
        help="If set, do not clean up intermediate files after coverage collection.",
    )
    argv = parser.parse_args()

    argv.output_dir = Path(argv.output_dir).absolute()
    argv.window_size = int(argv.window_size) * 60  # Convert minutes to seconds

    return ParsedArgv(
        output_dir=argv.output_dir,
        target_program=argv.target_program,
        fuzzer=argv.fuzzer,
        experiment_name=argv.experiment_name,
        fuzz_id=argv.fuzz_id,
        no_cleanup=argv.no_cleanup,
        window_size=argv.window_size
    )

def main():
    parsed_argv = parse_argv()

    fuzzer: Fuzzer = FuzzerFactory.create_fuzzer(
        output_dir=parsed_argv.output_dir,
        target_program=parsed_argv.target_program,
        fuzzer_name=parsed_argv.fuzzer,
        experiment_name=parsed_argv.experiment_name,
        fuzz_id=parsed_argv.fuzz_id
    )

    # 1. Initialization
    fuzzer.init_coverage()
    fuzzer.coverage.init_loggers()

    success = fuzzer.coverage.check_requirements()
    if not success:
        fuzzer.coverage.main_logger.error("Coverage requirements check failed.")
        sys.exit(1)
    

    # 2. Organization
    fuzzer.coverage.main_logger.info("Organizing inputs for coverage analysis.")
    success = fuzzer.coverage.organize_inputs(window_size=parsed_argv.window_size)
    if not success:
        fuzzer.coverage.main_logger.error("Failed to organize inputs for coverage analysis.")
        sys.exit(1)
    fuzzer.coverage.main_logger.info("Input organization complete.")


    # 3. Execution
    fuzzer.coverage.main_logger.info("[BEGIN] Starting coverage collection.")
    tasks = {
        "gcov": fuzzer.coverage.run_gcov,
        "bbcov": fuzzer.coverage.run_bbcov
    }

    with ThreadPoolExecutor(max_workers=len(tasks)) as executor:
        futures = {
            name: executor.submit(task, parsed_argv.window_size)
            for name, task in tasks.items()
        }
        for name, future in futures.items():
            try:
                success = future.result()
                if not success:
                    fuzzer.coverage.main_logger.error(f"Coverage collection failed for {name}.")
                    sys.exit(1)
                else:
                    fuzzer.coverage.main_logger.info(f"Coverage collection completed successfully for {name}.")
            except Exception as e:
                fuzzer.coverage.main_logger.error(f"Exception during coverage collection for {name}: {e}")
                sys.exit(1)
    fuzzer.coverage.main_logger.info("[COMPLETE] Coverage collection completed successfully for all tools.")

    if not parsed_argv.no_cleanup:
        fuzzer.coverage.cleanup()
    
    fuzzer.coverage.main_logger.info("[COMPLETE] Gracefully exiting coverage collection.")


if __name__ == "__main__":
    main()
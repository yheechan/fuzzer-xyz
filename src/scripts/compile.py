import argparse
import sys
import shutil
import time

from pathlib import Path
from dataclasses import dataclass

ROOT_DIR = Path(__file__).resolve().parent.parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from src.utils.constants import (
    TARGET_SUBJECTS,
    BASELINE_FUZZERS,
    PACKAGE_MAP,
)
from src.compiler.compile_utils import (
    make_bitcode,
    compile_asan,
    compile_coverage_driver,
)
from src.compiler.build_logics import (
    BUILD_LOGICS_MAP
)
from src.utils.common_utils import (
    check_llvm_tools,
    print_elapsed_time
)

from src.fuzzer.fuzzer_factory import FuzzerFactory

@dataclass
class ParsedArgv:
    output_dir: Path
    target_program: str
    fuzzer: str


def parse_argv() -> ParsedArgv:
    parser = argparse.ArgumentParser(
        description="Compile subject programs with custom LLVM passes"
    )

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

    argv = parser.parse_args()
    argv.output_dir = Path(argv.output_dir).absolute()

    return ParsedArgv(
        output_dir=argv.output_dir,
        target_program=argv.target_program,
        fuzzer=argv.fuzzer,
    )

def init_output_dir(output_dir: Path) -> bool:
    if output_dir.is_file():
        print(f"{output_dir} is an existing file, please specify a directory.")
        return False

    if output_dir.is_dir():
        print(
            f"Output directory {output_dir} already exists. Checking if we can use it..."
        )
        is_analysis_dir_fn = output_dir / ".is_analysis_dir"

        if not is_analysis_dir_fn.exists():
            print(
                f"Output directory {output_dir} already exists, but it seems risky to just remove and use it."
            )
            return False

        num_result_dirs = len(list(output_dir.glob("*_*")))

        if num_result_dirs > 0:
            # Ask user to confirm if they want to remove the existing directory
            print(
                f"Output directory {output_dir} already exists and contains {num_result_dirs} result directories. Do you want to remove it and use it for new analysis? (y/n/c)"
            )
            answer = input().strip().lower()
            if answer == "n":
                print("Aborting...")
                return False
            elif answer == "c":
                print("Continuing without removing the existing directory...")
                return True

        print(f"Removing existing output directory {output_dir}...")
        shutil.rmtree(output_dir)

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=False)

    is_analysis_dir_fn = output_dir / ".is_analysis_dir"
    is_analysis_dir_fn.touch()

    drivers_dir = output_dir / "drivers"
    drivers_dir.mkdir(parents=True, exist_ok=False)

    system_drivers_dir = drivers_dir / "system_drivers"
    system_drivers_dir.mkdir(parents=True, exist_ok=False)

    return True

def main():
    parsed_argv = parse_argv()

    success = init_output_dir(parsed_argv.output_dir)
    if not success:
        return None
    
    fuzzer = FuzzerFactory.create_fuzzer(
        parsed_argv.output_dir,
        parsed_argv.target_program,
        parsed_argv.fuzzer
    )
    
    success = check_llvm_tools([fuzzer.CC, fuzzer.CXX, fuzzer.FUZZER])
    if not success:
        print("Please make sure all required LLVM tools and AFL tools are installed and in PATH.")
        return
    
    target_program = parsed_argv.target_program

    # copy the program
    output_dir = parsed_argv.output_dir
    orig_build_dir = output_dir / "drivers" / "orig_build"
    orig_build_dir.mkdir(parents=True, exist_ok=True)
    sys_driver_dir = output_dir / "drivers" / "system_drivers"
    sys_driver_dir.mkdir(parents=True, exist_ok=True)
    orig_prog_fn = orig_build_dir / "install" / "bin" / target_program
    baseline_build_dir = output_dir / "drivers" / "baseline_build"
    baseline_build_dir.mkdir(parents=True, exist_ok=True)
    baseline_orig_prog_fn = baseline_build_dir / "install" / "bin" / target_program

    begin_time = time.time()

    if orig_prog_fn.exists():
        print(f"Program {orig_prog_fn} already exists, skipping build...")
    else:
        package_name = PACKAGE_MAP[target_program]
        build_logic = BUILD_LOGICS_MAP[package_name]

        success = build_logic(orig_build_dir)
        if not success:
            print(f"Failed to build {target_program}")
            return

        if not orig_prog_fn.exists():
            print(f"Built program {orig_prog_fn} does not exist")
            return
        

    if baseline_orig_prog_fn.exists():
        print(f"Baseline program {baseline_orig_prog_fn} already exists, skipping build...")
    else:
        package_name = PACKAGE_MAP[target_program]
        build_logic = BUILD_LOGICS_MAP[package_name]

        success = build_logic(baseline_build_dir, for_baseline_fuzz=True)
        if not success:
            print(f"Failed to build baseline version of {target_program}")
            return
        
        if not baseline_orig_prog_fn.exists():
            print(f"Built baseline program {baseline_orig_prog_fn} does not exist")
            return

    copy_dest_fn = sys_driver_dir / target_program
    shutil.copyfile(orig_prog_fn, copy_dest_fn)

    success = make_bitcode(copy_dest_fn)
    if not success:
        print("Failed to make bitcode")
        return

    success = compile_asan(copy_dest_fn, orig_prog_fn)
    if not success:
        print("Failed to compile system-level driver")
        return

    print_elapsed_time(begin_time, "Finished compiling system-level driver")

    success = compile_coverage_driver(copy_dest_fn, orig_prog_fn)
    if not success:
        print("Failed to compile coverage driver")
        return

    print_elapsed_time(begin_time, "Finished compiling coverage driver")

    
    success = fuzzer.compile()
    if not success:
        print(f"Failed to compile fuzzer: {fuzzer}")
        return

    print("Finished compiling drivers")
    return


if __name__ == "__main__":
    main()
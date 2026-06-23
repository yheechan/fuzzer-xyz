import multiprocessing
import shutil
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from src.utils.common_utils import (
    run_subprocess,
    remove_file
)
from src.utils.log import (
    get_debug_logger,
)
from src.utils.constants import (
    PASS_DIRS,
    PASS_OPTIONS,
    PassEnum,
    BB_COV_BUILD
)

manager = multiprocessing.Manager()
stop_event = manager.Event()


def run_opt(
    pass_name: PassEnum,
    in_fn: Path,
    out_fn: Path,
    additional_args: list[str] = [],
) -> bool:

    pass_dir = PASS_DIRS[pass_name]

    pass_fn = pass_dir / pass_name.value

    pass_opt = PASS_OPTIONS[pass_name]

    cmd = [
        "opt",
        "-load-pass-plugin",
        str(pass_fn),
        pass_opt,
        "-o",
        str(out_fn),
        str(in_fn),
    ] + additional_args

    outs, errs = run_subprocess(cmd, get_output=True)

    if not out_fn.exists():
        debug_logger = get_debug_logger("run_opt")
        debug_logger.error(f"Failed to generate {out_fn}")
        debug_logger.error(f"cmd = {' '.join(cmd)}")
        debug_logger.error(f"outs : {outs}")
        debug_logger.error(f"errs : {errs}")

        return False

    return True


def make_bitcode(prog: Path) -> bool:
    if shutil.which("get-bc") is None:
        print("get-bc not found in PATH")
        return False

    cmd = ["get-bc", str(prog)]
    run_subprocess(cmd)

    out_fn = prog.with_suffix(".bc")

    if not out_fn.exists():
        print(f"Failed to generate {out_fn}")
        return False

    cmd = ["file", str(out_fn)]
    outs, _ = run_subprocess(cmd, get_output=True)

    if "bitcode" not in outs:
        print(f"Can't recognize file : {out_fn}")
        return False

    return True


def handle_sigint(signum, frame):
    print("Received SIGINT, terminating...")
    stop_event.set()


def get_ld_flags(target_prog: Path) -> list[str]:
    cmd = ["ldd", str(target_prog)]

    outs, _ = run_subprocess(cmd, get_output=True)
    ldflags = []
    for line in outs.split("\n"):
        line = line.strip()
        if line == "":
            continue
        parts = line.split("=>")
        if len(parts) < 2:
            continue

        lib_name = parts[0].strip()
        if lib_name.startswith("lib"):
            lib_name = lib_name[3:]

        if ".so" in lib_name:
            lib_name = lib_name.split(".so")[0]

        if lib_name == "c":
            continue

        lib_path = parts[1].strip().split(" ")[0]
        lib_path = "/".join(lib_path.split("/")[:-1])

        if lib_path == "":
            continue

        ldflags.append(f"-L{lib_path}")
        ldflags.append(f"-l{lib_name}")
        ldflags.append(f"-Wl,-rpath,{lib_path}")

    basename = target_prog.name
    if basename == "mpg123":
        ## TODO: generalize ...
        lib_dir = target_prog.parent.parent / "lib"
        if not lib_dir.exists():
            print(f"Lib directory not found at {lib_dir}")
            return ldflags
        ldflags.append(f"-L{lib_dir}")
        ldflags.append(f"-Wl,-rpath,{lib_dir}")
        ldflags.append("-l:libmpg123.a")
        ldflags.append("-l:libout123.a")

    return ldflags

def compile_asan(target_prog: Path, orig_prog_path: Path) -> bool:
    input_bc_fn = target_prog.with_suffix(".bc")
    driver_asan_fn = target_prog.with_suffix(".asan")

    remove_file(driver_asan_fn)

    ld_flags = get_ld_flags(orig_prog_path)
    
    cmd = [
        "clang++",
        "-o",
        str(driver_asan_fn),
        str(input_bc_fn),
        "-fsanitize=address",
        "-O0",
        "-g",
    ] + ld_flags

    print("Compiling system-level driver for ASAN...")
    run_subprocess(cmd)

    if not driver_asan_fn.exists():
        print("Failed to generate ", driver_asan_fn)
        print(f"cmd = {' '.join(cmd)}")
        return False

    return True

def compile_coverage_driver(target_prog: Path, orig_prog_path: Path) -> bool:
    input_bc_fn = target_prog.with_suffix(".bc")
    driver_cov_fn = target_prog.with_suffix(".cov.bc")
    driver_cov_out = target_prog.with_suffix(".cov")

    driver_path_fn = target_prog.with_suffix(".path.bc")
    driver_path_out = target_prog.with_suffix(".path")

    for fn in [
        driver_cov_fn,
        driver_cov_out,
        driver_path_fn,
        driver_path_out,
    ]:
        remove_file(fn)

    ## 1. compile system level driver bitcode
    ld_flags = get_ld_flags(orig_prog_path)

    ## 3. compile binary for BB cov
    print("Running BB coverage analysis pass...")
    success = run_opt(PassEnum.BB_COV_PASS, input_bc_fn, driver_cov_fn)
    if not success:
        return False

    cmd = [
        "clang++",
        "-o",
        str(driver_cov_out),
        str(driver_cov_fn),
        "-O0",
        "-g",
        "-L",
        str(BB_COV_BUILD),
        "-l:bb_cov_rt.a",
    ] + ld_flags

    print("Compiling system-level driver for coverage...")
    run_subprocess(cmd)

    if not driver_cov_out.exists():
        print("Failed to generate ", driver_cov_out)
        print(f"cmd = {' '.join(cmd)}")
        return False

    ## 4. Compile binary for Path cov
    print("Running Path coverage analysis pass...")
    success = run_opt(PassEnum.PATH_COV_PASS, input_bc_fn, driver_path_fn)
    if not success:
        return False

    cmd = [
        "clang++",
        "-o",
        str(driver_path_out),
        str(driver_path_fn),
        "-O2",
        "-L",
        str(BB_COV_BUILD),
        "-l:path_cov_rt.a",
    ] + ld_flags

    print("Compiling system-level driver for path coverage...")
    run_subprocess(cmd)
    if not driver_path_out.exists():
        print("Failed to generate ", driver_path_out)
        print(f"cmd = {' '.join(cmd)}")
        return False

    return True

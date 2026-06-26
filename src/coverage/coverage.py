import json
import sys
import shutil
import bisect
import re
import subprocess

from datetime import datetime
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from src.utils.constants import (
    SUBJECT_ARGV,
    VENV_ROOT,
    PROJ_ROOT
)
from src.utils.log import (
    setup_task_logger
)
from src.utils.common_utils import (
    unpack_targz
)

GCOVR = VENV_ROOT / "bin" / "gcovr"
BBCOV_STAT_PY = PROJ_ROOT / "bb_cov" / "scripts" / "get_bbcov_stat.py"

class Coverage:
    fuzzer_name: str
    target_program: str
    fuzz_id: str

    fuzz_outputs_dirp: Path
    queue_dirp: Path
    plot_data_fp: Path

    logs_dirp: Path
    coverage_dirp: Path

    baseline_build_dirp: Path
    system_drivers_dirp: Path
    
    read_plot_data_func: callable

    def __init__(self, fuzzer_name: str, target_program: str, fuzz_id: str, fuzz_outputs_dirp: Path, queue_dirp: Path, plot_data_fp: Path, logs_dirp: Path, coverage_dirp: Path, baseline_build_dirp: Path, system_drivers_dirp: Path, read_plot_data_func: callable):
        self.fuzzer_name = fuzzer_name
        self.target_program = target_program
        self.fuzz_id = fuzz_id
        self.fuzz_outputs_dirp = fuzz_outputs_dirp
        self.queue_dirp = queue_dirp
        self.plot_data_fp = plot_data_fp
        self.logs_dirp = logs_dirp
        self.coverage_dirp = coverage_dirp
        self.baseline_build_dirp = baseline_build_dirp
        self.system_drivers_dirp = system_drivers_dirp
        self.read_plot_data_func = read_plot_data_func

    def init_loggers(self):
        if not self.logs_dirp.exists():
            self.logs_dirp.mkdir(parents=True, exist_ok=True)

        self.main_logger = setup_task_logger(
            name="coverage_main",
            log_file=self.logs_dirp / f"{self.fuzz_id}.coverage.log",
            stdout=True
        )

        self.gcov_logger = setup_task_logger(
            name="coverage_gcov",
            log_file=self.logs_dirp / f"{self.fuzz_id}.gcov.log",
            stdout=False
        )

        self.bbcov_logger = setup_task_logger(
            name="coverage_bbcov",
            log_file=self.logs_dirp / f"{self.fuzz_id}.bbcov.log",
            stdout=False
        )
    
    def cleanup(self):
        fuzz_dirp = self.fuzz_outputs_dirp / self.fuzz_id
        if fuzz_dirp.exists():
            shutil.rmtree(fuzz_dirp)

    def check_requirements(self) -> bool:
        for tool in ["llvm-config", "llvm-cov", "gcovr", GCOVR, BBCOV_STAT_PY]:
            if not shutil.which(tool):
                self.main_logger.error(f"Required tool '{tool}' is not installed or not in PATH.")
                return False

        self.gcov_fp = self.baseline_build_dirp / "install" / "bin" / self.target_program
        if not self.gcov_fp.exists():
            self.main_logger.error(f"Baseline build of target program '{self.target_program}' not found at {self.gcov_fp}.")
            return False

        self.bbcov_fp = self.system_drivers_dirp / f"{self.target_program}.cov"
        if not self.bbcov_fp.exists():
            self.main_logger.error(f"System driver for target program '{self.target_program}' not found at {self.bbcov_fp}.")
            return False
        
        self.fuzz_tar_gz = self.fuzz_outputs_dirp / f"{self.fuzz_id}.tar.gz"
        if not self.fuzz_tar_gz.exists():
            self.main_logger.error(f"Fuzzing output tarball '{self.fuzz_tar_gz}' not found.")
            return False
        
        fuzz_dirp = self.fuzz_outputs_dirp / self.fuzz_id
        if fuzz_dirp.exists():
            self.main_logger.info(f"Fuzzing output directory '{fuzz_dirp}' already exists. Cleaning up before unpacking.")
            shutil.rmtree(fuzz_dirp)
        
        success = unpack_targz(self.fuzz_tar_gz, self.fuzz_outputs_dirp)
        if not success:
            self.main_logger.error(f"Failed to unpack fuzzing output tarball '{self.fuzz_tar_gz}'.")
            return False
        
        if not self.queue_dirp.exists():
            self.main_logger.error(f"Queue directory '{self.queue_dirp}' not found after unpacking fuzzing output.")
            return False
        
        if not self.plot_data_fp.exists():
            self.main_logger.error(f"Plot data file '{self.plot_data_fp}' not found after unpacking fuzzing output.")
            return False
        
        if not self.coverage_dirp.exists():
            self.coverage_dirp.mkdir(parents=True, exist_ok=True)

        return True

    def organize_inputs(self, window_size: int = 600) -> bool:
        self.organized_inputs: dict[int, list[Path]] = {}

        # 1. corpus growth over time from plot data
        samples = self.read_plot_data_func(self.plot_data_fp)
        if not samples:
            self.main_logger.error(f"No valid samples found in plot data file '{self.plot_data_fp}'.")
            return False
        
        rel_times = [s[0] for s in samples]
        counts = [s[1] for s in samples]

        def count_at(t_sec: int) -> int:
            """corpus_count as of relative time t (last sample with rel_time <= t)."""
            idx = bisect.bisect_right(rel_times, t_sec) - 1
            return counts[idx] if idx >= 0 else 0
        
        # 2. queue files in id order; paths[i] is the input with id i
        id_re = re.compile(r"id:(\d+)")
        id_files: list[tuple[int, Path]] = []
        for entry in self.queue_dirp.iterdir():
            if not entry.is_file():
                continue
            match = id_re.search(entry.name)
            if match is None:
                continue
            id_files.append((int(match.group(1)), entry))
        id_files.sort(key=lambda item: item[0])
        paths = [path for _, path in id_files]

        if not paths:
            self.main_logger.error(f"No valid queue files found in '{self.queue_dirp}'.")
            return False

        # 3. slice id-sorted inputs by the corpus_count at each frame boundary
        last_time = rel_times[-1]
        num_frames = max(1, -(-last_time // window_size))  # ceil division
        prev_count = 0
        for frame in range(num_frames):
            end_sec = (frame + 1) * window_size
            # clamp to available files; corpus_count should never exceed len(paths),
            # but stay safe against plot_data/queue mismatches.
            cur_count = min(count_at(end_sec), len(paths))
            cur_count = max(cur_count, prev_count)
            self.organized_inputs[frame] = paths[prev_count:cur_count]
            prev_count = cur_count

        self.main_logger.info(
            f"Organized {prev_count} inputs (of {len(paths)} queue files) from "
            f"{self.queue_dirp} into {num_frames} frame(s) of {window_size}s "
            f"using {self.plot_data_fp.name}."
        )

        return True

    def run_gcov(self, window_size: int = 600) -> bool:
        """For each frame, run gcov on the frame's inputs and extract line/branch coverage."""
        start_time = datetime.now()
        gcov_coverage = {}

        # Delete all *.gcda files from baseline_build_dirp / target_program to reset coverage counters before replaying the fuzz inputs
        gcda_files = list((self.baseline_build_dirp).rglob("*.gcda"))
        for gcda_file in gcda_files:
            gcda_file.unlink()
        self.gcov_logger.info(f"Deleted {len(gcda_files)} .gcda files to reset coverage counters.")

        cumulative = 0
        for frame, inputs in sorted(self.organized_inputs.items()):
            start_min = frame * window_size // 60
            end_min = (frame + 1) * window_size // 60
            range = f"{start_min:>3}-{end_min:>3}"
            cumulative += len(inputs)

            self.gcov_logger.info(f"[GCOV] Processing Frame {frame:>3} [{range} min]: +{len(inputs)} new, {cumulative} cumulative")

            
            gcov_coverage[frame] = {
                "range": range,
                "num_inputs": len(inputs),
                "cumulative": cumulative
            }

            # run inputs
            num_timeouts = 0
            for input_path in inputs:
                # replace @@ with input path and run gcov
                subject_args = SUBJECT_ARGV[self.target_program]
                subject_args = [arg.replace("@@", str(input_path)) for arg in subject_args]

                cmd = [self.gcov_fp] + subject_args
                try:
                    subprocess.run(
                        cmd,
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                        stdin=subprocess.DEVNULL,
                        cwd= self.baseline_build_dirp,
                        timeout=1, # 1 seconds
                    )
                except subprocess.TimeoutExpired:
                    # Flaky/hanging input: subprocess.run already killed it. Its .gcda
                    # is not flushed (the process is killed, not exited), so it adds
                    # no coverage for this run — acceptable for a hang.
                    num_timeouts += 1
            self.gcov_logger.info(
                f"Finished running {len(inputs)} inputs for Frame {frame:>3} "
                f"[{range} min] ({num_timeouts} timed out)."
            )

            # extract line/branch coverage from .gcda files and save to .gcov files
            gcov_json_fn = self.baseline_build_dirp / f"{self.target_program}.{self.fuzz_id}.gcov.json"

            gcovr_cmd = [
                GCOVR,
                ".",
                "--gcov-executable",
                "llvm-cov gcov",
                "--gcov-ignore-errors=no_working_dir_found",
                "--gcov-ignore-parse-errors=all",
                "--gcov-ignore-parse-errors=suspicious_hits.warn_once_per_file",
                "--merge-mode-functions=merge-use-line-min",
                "--exclude", ".*conftest.*",
                "--json-summary",
                "-o",
                gcov_json_fn
            ]
            subprocess.run(
                gcovr_cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                stdin=subprocess.DEVNULL,
                cwd=self.baseline_build_dirp
            )

            # record line/branch coverage information for this frame
            with open(gcov_json_fn) as f:
                gcov_data = json.load(f)
                gcov_coverage[frame]["function_covered"] = gcov_data.get("function_covered", -1)
                gcov_coverage[frame]["line_covered"] = gcov_data.get("line_covered", -1)
                gcov_coverage[frame]["branch_covered"] = gcov_data.get("branch_covered", -1)
                gcov_coverage[frame]["function_total"] = gcov_data.get("function_total", -1)
                gcov_coverage[frame]["line_total"] = gcov_data.get("line_total", -1)
                gcov_coverage[frame]["branch_total"] = gcov_data.get("branch_total", -1)

            self.gcov_logger.info(f"Extracted coverage for Frame {frame:>3} [{range} min]: "
                        f"{gcov_coverage[frame]['function_covered']}/{gcov_coverage[frame]['function_total']} functions, "
                        f"{gcov_coverage[frame]['line_covered']}/{gcov_coverage[frame]['line_total']} lines, "
                        f"{gcov_coverage[frame]['branch_covered']}/{gcov_coverage[frame]['branch_total']} branches.")

        # save coverage information to a csv file
        coverage_csv_fn = self.coverage_dirp / f"{self.target_program}.{self.fuzz_id}.gcov.csv"

        with open(coverage_csv_fn, "w") as f:
            f.write("frame,range,num_inputs,cumulative,function_covered,function_total,line_covered,line_total,branch_covered,branch_total\n")
            for frame in sorted(gcov_coverage):
                data = gcov_coverage[frame]
                f.write(f"{frame},{data['range']},{data['num_inputs']},{data['cumulative']},"
                        f"{data.get('function_covered', -1)},{data.get('function_total', -1)},"
                        f"{data.get('line_covered', -1)},{data.get('line_total', -1)},"
                        f"{data.get('branch_covered', -1)},{data.get('branch_total', -1)}\n")

        self.gcov_logger.info(f"Saved coverage information for all frames to {coverage_csv_fn}.")
        end_time = datetime.now()
        elapsed = (end_time - start_time).total_seconds() / 60
        self.gcov_logger.info(f"GCOV coverage extraction complete in {elapsed:.1f} min.")

        return True


    def run_bbcov(self, window_size: int = 600) -> bool:
        """For each frame, run the bbcov driver on the frame's inputs and extract basic-block coverage."""
        start_time = datetime.now()
        bbcov_coverage = {}

        bbcov_file = self.system_drivers_dirp / f"{self.target_program}.{self.fuzz_id}.bbcov"
        if bbcov_file.exists():
            bbcov_file.unlink()
            self.bbcov_logger.info(f"Deleted existing bbcov file {bbcov_file} to reset coverage counters.")

        cumulative = 0
        for frame, inputs in sorted(self.organized_inputs.items()):
            start_min = frame * window_size // 60
            end_min = (frame + 1) * window_size // 60
            range = f"{start_min:>3}-{end_min:>3}"
            cumulative += len(inputs)
            self.bbcov_logger.info(f"[BBCOV] Processing Frame {frame:>3} [{range} min]: +{len(inputs)} new, {cumulative} cumulative")

            bbcov_coverage[frame] = {
                "range": range,
                "num_inputs": len(inputs),
                "cumulative": cumulative
            }

            # run inputs
            num_timeouts = 0
            for input_path in inputs:
                # replace @@ with input path and run bbcov driver
                subject_args = SUBJECT_ARGV[self.target_program]
                subject_args = [arg.replace("@@", str(input_path)) for arg in subject_args]

                cmd = [self.bbcov_fp] + subject_args + [bbcov_file]
                try:
                    res = subprocess.run(
                        cmd,
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                        stdin=subprocess.DEVNULL,
                        cwd= self.system_drivers_dirp,
                        timeout=1, # 1 seconds
                    )
                except subprocess.TimeoutExpired:
                    # Flaky/hanging input: subprocess.run already killed it. Its .bbcov
                    # is not flushed (the process is killed, not exited), so it adds
                    # no coverage for this run — acceptable for a hang.
                    num_timeouts += 1
            self.bbcov_logger.info(
                f"Finished running {len(inputs)} inputs for Frame {frame:>3} "
                f"[{range} min] ({num_timeouts} timed out)."
            )

            bbcov_json_fn = self.system_drivers_dirp / f"{self.target_program}.{self.fuzz_id}.bbcov.json"
            if bbcov_json_fn.exists():
                bbcov_json_fn.unlink()

            extract_bbcov_cmd = [
                "python3",
                BBCOV_STAT_PY,
                str(bbcov_file),
                str(bbcov_json_fn)
            ]
            subprocess.run(
                extract_bbcov_cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                stdin=subprocess.DEVNULL,
            )

            # record basic-block coverage information for this frame
            with open(bbcov_json_fn) as f:
                bbcov_data = json.load(f)
                bbcov_coverage[frame]["function_covered"] = bbcov_data.get("accumulated_func_cov", -1)
                bbcov_coverage[frame]["line_covered"] = bbcov_data.get("accumulated_line_cov", -1)
                bbcov_coverage[frame]["branch_covered"] = bbcov_data.get("accumulated_bb_cov", -1)
                bbcov_coverage[frame]["function_total"] = bbcov_data.get("total_funcs", -1)
                bbcov_coverage[frame]["line_total"] = bbcov_data.get("total_lines", -1)
                bbcov_coverage[frame]["branch_total"] = bbcov_data.get("total_bbs", -1)

            self.bbcov_logger.info(f"Extracted coverage for Frame {frame:>3} [{range} min]: "
                        f"{bbcov_coverage[frame]['function_covered']}/{bbcov_coverage[frame]['function_total']} functions, "
                        f"{bbcov_coverage[frame]['line_covered']}/{bbcov_coverage[frame]['line_total']} lines, "
                        f"{bbcov_coverage[frame]['branch_covered']}/{bbcov_coverage[frame]['branch_total']} basic blocks.")
            
        # save coverage information to a csv file
        coverage_csv_fn = self.coverage_dirp / f"{self.target_program}.{self.fuzz_id}.bbcov.csv"
        with open(coverage_csv_fn, "w", newline="") as f:
            f.write("frame,range,num_inputs,cumulative,function_covered,function_total,line_covered,line_total,branch_covered,branch_total\n")
            for frame in sorted(bbcov_coverage):
                data = bbcov_coverage[frame]
                f.write(f"{frame},{data['range']},{data['num_inputs']},{data['cumulative']},"
                        f"{data.get('function_covered', -1)},{data.get('function_total', -1)},"
                        f"{data.get('line_covered', -1)},{data.get('line_total', -1)},"
                        f"{data.get('branch_covered', -1)},{data.get('branch_total', -1)}\n")

        self.bbcov_logger.info(f"Saved coverage information for all frames to {coverage_csv_fn}.")
        end_time = datetime.now()
        elapsed = (end_time - start_time).total_seconds() / 60
        self.bbcov_logger.info(f"BBCOV coverage extraction complete in {elapsed:.1f} min.")

        return True

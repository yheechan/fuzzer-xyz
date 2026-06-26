import os
import re
import shutil
import sys
import subprocess
import time

from datetime import timedelta
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from src.utils.constants import (
    PROJ_ROOT,
    ANGORA_CC,
    ANGORA_CXX,
    ANGORA_FUZZER,
    ANGORA_ROOT,
)
from src.utils.configs import (
    ANGORA_RUN_DIR,
    SUN_LEN,
    LLVM12_ROOT,
)
from src.compiler.compile_utils import (
    get_ld_flags,
    make_bitcode,
)
from src.utils.common_utils import (
    remove_file,
)
from src.fuzzer.fuzzer import Fuzzer
from src.coverage.coverage import Coverage

# External taint-source model for open64() (libav/ffmpeg call open64 under
# -D_FILE_OFFSET_BITS=64). open64_rule.c is committed; the .o is compiled on demand.
ANGORA_RULES_DIR = PROJ_ROOT / "data" / "angora_rules"

class AngoraFuzzer(Fuzzer):
    def __init__(
            self,
            output_dir: Path,
            target_program: str,
            experiment_name: str = None,
            NUM_FUZZERS: int = 4,
            fuzz_id: str = None
        ):
        super().__init__(output_dir, target_program, experiment_name, NUM_FUZZERS, fuzz_id)
        self.CC = str(ANGORA_CC)
        self.CXX = str(ANGORA_CXX)
        self.FUZZER = str(ANGORA_FUZZER)

    # ------------------------------------------------------------------ #
    # compile: build one LLVM-12 whole-program .bc (per-target build      #
    # logic), then turn that single .bc into .fast and .taint generically.#
    # NOTE: compile() runs from compile.py before the fuzz logger exists, #
    # so this path uses print(), not self.logger.                         #
    # ------------------------------------------------------------------ #
    def _angora_env(self, rule_list: Path = None, custom_obj: Path = None, track: bool = False) -> dict:
        """angora-clang must use the LLVM-12 backend its prebuilt passes need."""
        env = os.environ.copy()
        env["PATH"] = str(LLVM12_ROOT / "bin") + os.pathsep + env.get("PATH", "")
        ld_paths = [str(ANGORA_ROOT / "bin" / "lib"), str(LLVM12_ROOT / "lib")]
        if env.get("LD_LIBRARY_PATH"):
            ld_paths.append(env["LD_LIBRARY_PATH"])
        env["LD_LIBRARY_PATH"] = os.pathsep.join(ld_paths)
        env["ANGORA_CC"] = str(LLVM12_ROOT / "bin" / "clang")
        env["ANGORA_CXX"] = str(LLVM12_ROOT / "bin" / "clang++")
        if track:
            env["USE_TRACK"] = "1"
        if rule_list is not None:
            env["ANGORA_TAINT_RULE_LIST"] = str(rule_list)
        if custom_obj is not None:
            env["ANGORA_TAINT_CUSTOM_RULE"] = str(custom_obj)
        return env

    def _ensure_open64_obj(self) -> Path:
        src = ANGORA_RULES_DIR / "open64_rule.c"
        obj = ANGORA_RULES_DIR / "open64_rule.o"
        if not src.exists():
            print(f"Missing open64 taint-source model: {src}")
            return None
        res = subprocess.run(
            [str(LLVM12_ROOT / "bin" / "clang"), "-c", "-fPIC", "-O2", str(src), "-o", str(obj)]
        )
        if res.returncode != 0 or not obj.exists():
            print("Failed to compile open64_rule.o")
            return None
        return obj

    def _build_target_bc(self, work_dir: Path) -> Path:
        """Build the target into a whole-program LLVM-12, -fPIC .bc via gllvm.

        The bitcode's canonical home is system_drivers/<target>.angora.bc (next
        to the other drivers), which is also the cache key. `work_dir`
        (angora_build) is only the build workspace and is kept after extraction.
        """
        sys_dir = self.output_dir / "drivers" / "system_drivers"
        sys_dir.mkdir(parents=True, exist_ok=True)
        angora_bc = sys_dir / f"{self.target_program}.angora.bc"
        if angora_bc.exists():
            print(f"Reusing existing Angora bitcode: {angora_bc}")
            return angora_bc

        prog = work_dir / "install" / "bin" / self.target_program

        # Point gclang / get-bc at the LLVM-12 toolchain (angora-clang's backend).
        saved = {k: os.environ.get(k) for k in ("LLVM_COMPILER", "LLVM_COMPILER_PATH")}
        os.environ["LLVM_COMPILER"] = "clang"
        os.environ["LLVM_COMPILER_PATH"] = str(LLVM12_ROOT / "bin")
        try:
            work_dir.mkdir(parents=True, exist_ok=True)
            if not self.build_logic(work_dir, for_angora=True):
                print(f"Failed to build {self.target_program} for Angora bitcode")
                return None
            if not prog.exists():
                print(f"Built program not found: {prog}")
                return None
            if not make_bitcode(prog):     # get-bc -> <work_dir>/install/bin/<target>.bc
                print(f"Failed to extract bitcode from {prog}")
                return None
        finally:
            for k, v in saved.items():
                if v is None:
                    os.environ.pop(k, None)
                else:
                    os.environ[k] = v

        shutil.copyfile(prog.with_suffix(".bc"), angora_bc)
        print(f"Saved Angora bitcode to {angora_bc}")
        return angora_bc

    def _compile_drivers_from_bc(self, bc_fn: Path, orig_prog_fn: Path) -> bool:
        """Generic: one .bc -> <target>.fast and <target>.taint (no per-target logic)."""
        sys_dir = self.output_dir / "drivers" / "system_drivers"
        sys_dir.mkdir(parents=True, exist_ok=True)
        fast_fn = sys_dir / f"{self.target_program}.fast"
        taint_fn = sys_dir / f"{self.target_program}.taint"
        ld_flags = get_ld_flags(orig_prog_fn)

        # Drop any stale drivers first so a failed rebuild can't leave an old
        # binary that check_fuzz_targets() would accept as valid.
        remove_file(fast_fn)
        remove_file(taint_fn)

        # --- FAST (light instrumentation; default angora-clang mode) ---
        cmd = [str(ANGORA_CC), str(bc_fn), "-o", str(fast_fn)] + ld_flags
        print(f"Building {fast_fn.name} from bitcode...")
        res = subprocess.run(cmd, env=self._angora_env(), stderr=subprocess.PIPE, text=True)
        if res.returncode != 0 or not fast_fn.exists():
            print(f"FAST build failed:\n{res.stderr[-2000:]}")
            return False

        # --- TAINT (USE_TRACK / DFSan) ---
        # Seed extra taint-source models (open64 for libav/ffmpeg; dup/dup2/dup3
        # for libxml2 which dup()s the input fd) as custom, routed to our wrapper
        # object; then auto-harvest any remaining undefined dfs$<fn> externals
        # (zlib, modern glibc, ...) as discard.
        open64_obj = self._ensure_open64_obj()
        if open64_obj is None:
            return False
        rules_fn = sys_dir / f"{self.target_program}.taint_rules.txt"
        rules_fn.write_text(
            "fun:open64=custom\n"
            "fun:dup=custom\n"
            "fun:dup2=custom\n"
            "fun:dup3=custom\n"
        )

        harvested = []
        linked = False
        for attempt in range(1, 16):
            cmd = [str(ANGORA_CC), str(bc_fn), "-o", str(taint_fn)] + ld_flags
            env = self._angora_env(rule_list=rules_fn, custom_obj=open64_obj, track=True)
            res = subprocess.run(cmd, env=env, stderr=subprocess.PIPE, text=True)
            if res.returncode == 0 and taint_fn.exists():
                linked = True
                break
            syms = sorted(set(re.findall(r"dfs\$([A-Za-z0-9_]+)", res.stderr)))
            if not syms:
                print(f"TAINT build failed (no dfs$ symbols to harvest):\n{res.stderr[-2000:]}")
                return False
            with rules_fn.open("a") as f:
                for s in syms:
                    f.write(f"fun:{s}=uninstrumented\nfun:{s}=discard\n")
            harvested += syms
            print(f"[taint attempt {attempt}] harvested {len(syms)} external symbol(s)")

        if not linked:
            print("TAINT build did not converge after harvesting")
            return False
        if harvested:
            # Caveat: any program-internal function discarded here will not
            # propagate taint. Surface the list so it can be audited.
            print(f"WARNING: discarded {len(set(harvested))} dfs$ symbol(s) (taint will not "
                  f"flow through them): {', '.join(sorted(set(harvested)))}")

        print(f"Built {fast_fn.name} and {taint_fn.name}")
        return True

    def compile(self) -> bool:
        orig_prog_fn = self.output_dir / "drivers" / "orig_build" / "install" / "bin" / self.target_program
        if not orig_prog_fn.exists():
            print(f"Original program (needed for link flags) not found: {orig_prog_fn}")
            return False

        bc_fn = self._build_target_bc(self.output_dir / "drivers" / "angora_build")
        if bc_fn is None:
            return False

        return self._compile_drivers_from_bc(bc_fn, orig_prog_fn)

    def check_fuzz_targets(self) -> bool:
        self.taint_fn = self.output_dir / "drivers" / "system_drivers" / f"{self.target_program}.taint"
        if not self.taint_fn.exists():
            self.logger.error(f"Taint file does not exist: {self.taint_fn}")
            return False

        self.fast_fn = self.output_dir / "drivers" / "system_drivers" / f"{self.target_program}.fast"
        if not self.fast_fn.exists():
            self.logger.error(f"Fast file does not exist: {self.fast_fn}")
            return False
        
        if not ANGORA_RUN_DIR.exists():
            ANGORA_RUN_DIR.mkdir(parents=True, exist_ok=True)
        
        return True
    
    def wait_print_fuzz_stats(self):
        queue_dir = f"{self.fuzz_outputs_dirn}/queue"
        crash_dir = f"{self.fuzz_outputs_dirn}/crashes"
        begin_time = time.time()

        while not self.stop_requested and len(self.processes) > 0:
            for p in self.processes[:]:
                retcode = p.poll()
                if retcode is None:
                    continue
                self.logger.info(f"Fuzzer process {p.pid} exited with code {retcode}")
                self.processes.remove(p)

            num_inputs = len(os.listdir(queue_dir)) if os.path.exists(queue_dir) else 0
            num_crashes = len(os.listdir(crash_dir)) if os.path.exists(crash_dir) else 0

            elapsed = time.time() - begin_time
            elapsed_td = str(timedelta(seconds=int(elapsed)))
            self.logger.info(
                f"[elapsed time: {elapsed_td}] # queue: {num_inputs}, # crashes: {num_crashes}"
            )
            time.sleep(10)

    def fuzz(self) -> bool:
        self.fuzz_outputs_dirn = ANGORA_RUN_DIR / self.fuzz_id
        if len(str(self.fuzz_outputs_dirn)) > SUN_LEN:
            self.logger.error(f"Fuzz outputs directory path is too long: {self.fuzz_outputs_dirn}")
            self.logger.error(f"Path length: {len(str(self.fuzz_outputs_dirn))}, max allowed: {SUN_LEN}")
            return False

        fuzz_cmd = [
            self.FUZZER,
            "-i", str(self.init_seed_dirn),
            "-o", str(self.fuzz_outputs_dirn),
            "-j", str(self.NUM_FUZZERS),
            "-t", str(self.taint_fn),
            "--", str(self.fast_fn)
        ] + self.subject_argv

        self.logger.info(f"Started {self.__class__.__name__} processes. Press Ctrl+C to stop.")
        
        p = subprocess.Popen(
            fuzz_cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            stdin=subprocess.DEVNULL,
        )
        self.processes.append(p)

        self.wait_print_fuzz_stats()
        
        for p in self.processes:
            p.wait()
        self.processes.clear()

        self.dest_fuzz_outputs_dirn = self.outputs_dirn / self.fuzz_id
        shutil.move(str(self.fuzz_outputs_dirn), str(self.dest_fuzz_outputs_dirn))

        self.logger.info(f"{self.__class__.__name__} completed. Fuzz outputs moved to: {self.dest_fuzz_outputs_dirn}")
        
        return True

    def targets_on_server(self, server_address: str) -> bool:
        """
        Check if the fuzzing targets for the specified fuzzer are present on the server.

        Args:
            server_address (str): The address of the server.

        Returns:
            bool: True if the targets are present on the server, False otherwise.
        """

        targets = [
            self.taint_fn,
            self.fast_fn
        ]
        for target in targets:
            cmd = f"ssh {server_address} 'ls {target}'"
            result = subprocess.run(
                cmd,
                shell=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            
            result_str = result.stderr.decode().strip()
            on_server = False if "No such file or directory" in result_str else True
            if not on_server:
                print(f"[NO-TARGET] Fuzzing target {target} not found on server {server_address}.")
                return False

        return True


    def init_coverage(self) -> bool:
        experiment_dirp = self.output_dir / "baseline_fuzzing" / self.__class__.__name__ / self.experiment_name

        fuzz_id = self.fuzz_id

        fuzz_outputs_dirp = experiment_dirp / "fuzz_outputs"
        queue_dirp = fuzz_outputs_dirp / fuzz_id / "queue"
        plot_datafp = fuzz_outputs_dirp / fuzz_id / "angora.log"


        logs_dirp = experiment_dirp / "logs"
        coverage_dirp = experiment_dirp / "coverage"

        baseline_build_dirp = self.output_dir / "drivers" / "baseline_build"
        system_drivers_dirp = self.output_dir / "drivers" / "system_drivers"

        self.coverage = Coverage(
            fuzzer_name=self.__class__.__name__,
            target_program=self.target_program,
            fuzz_id=fuzz_id,
            fuzz_outputs_dirp=fuzz_outputs_dirp,
            queue_dirp=queue_dirp,
            plot_data_fp=plot_datafp,
            logs_dirp=logs_dirp,
            coverage_dirp=coverage_dirp,
            baseline_build_dirp=baseline_build_dirp,
            system_drivers_dirp=system_drivers_dirp,
            read_plot_data_func=self.read_plot_data,
        )

    def read_plot_data(self, plot_data_fn: Path) -> list[tuple[int, int]]:
        """Parse angora.log into a list of (relative_time_sec, corpus_count).

        Columns (per angora header):
            secs, density, num_inputs, num_hangs, num_crashes
        so index 0 is relative_time (seconds) and index 2 is corpus_count. Comment
        and malformed lines are skipped. Samples are returned in chronological order;
        corpus_count is monotonically non-decreasing.
        """
        samples: list[tuple[int, int]] = []
        with open(plot_data_fn) as f:
            for line in f:
                line = line.strip()
                cols = [c.strip() for c in line.split(",")]
                if len(cols) <= 2:
                    continue
                try:
                    rel_time = int(float(cols[0]))
                    corpus_count = int(cols[2])
                except ValueError:
                    continue
                samples.append((rel_time, corpus_count))
        return samples

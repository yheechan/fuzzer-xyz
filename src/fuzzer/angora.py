import os
import shutil
import sys
import signal
import subprocess
import time

from datetime import timedelta
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from src.utils.constants import (
    PACKAGE_MAP,
    ANGORA_CC,
    ANGORA_CXX,
    ANGORA_FUZZER,
)
from src.utils.configs import (
    NUM_FUZZERS,
    ANGORA_RUN_DIR,
    SUN_LEN
)
from src.fuzzer.fuzzer import Fuzzer
from src.builder.angora_builder import (
    BUILD_LOGICS_MAP
)

class AngoraFuzzer(Fuzzer):
    def __init__(
            self,
            output_dir: Path,
            target_program: str,
            experiment_name: str = None,
            fuzz_id: str = None
        ):
        super().__init__(output_dir, target_program, experiment_name, fuzz_id)
        self.CC = str(ANGORA_CC)
        self.CXX = str(ANGORA_CXX)
        self.FUZZER = str(ANGORA_FUZZER)
        self.package_name = PACKAGE_MAP[target_program]
        self.build_logic = BUILD_LOGICS_MAP[self.package_name]
    
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
        # Allow Ctrl+C to terminate the fuzzing process
        signal.signal(signal.SIGINT, self.handle_sigint)
        self.logger.info(f"Starting fuzzer processes...")
        self.logger.info(f"\tFuzzer: {self.FUZZER}")
        self.logger.info(f"\tTarget Program: {self.target_program}")
        self.logger.info(f"\tFuzz ID: {self.fuzz_id}")

        self.fuzz_outputs_dirn = ANGORA_RUN_DIR / self.fuzz_id
        if len(str(self.fuzz_outputs_dirn)) > SUN_LEN:
            self.logger.error(f"Fuzz outputs directory path is too long: {self.fuzz_outputs_dirn}")
            self.logger.error(f"Path length: {len(str(self.fuzz_outputs_dirn))}, max allowed: {SUN_LEN}")
            return False

        fuzz_cmd = [
            self.FUZZER,
            "-i", str(self.init_seed_dirn),
            "-o", str(self.fuzz_outputs_dirn),
            "-j", str(NUM_FUZZERS),
            "-t", str(self.taint_fn),
            "--", str(self.fast_fn)
        ] + self.subject_argv

        p = subprocess.Popen(
            fuzz_cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            stdin=subprocess.DEVNULL,
        )
        self.processes.append(p)

        self.logger.info("Started fuzzing processes. Press Ctrl+C to stop.")

        self.wait_print_fuzz_stats()
        
        for p in self.processes:
            p.wait()
        self.processes.clear()

        self.dest_fuzz_outputs_dirn = self.outputs_dirn / self.fuzz_id
        shutil.move(str(self.fuzz_outputs_dirn), str(self.dest_fuzz_outputs_dirn))

        self.logger.info(f"Fuzzing completed. Fuzz outputs moved to: {self.dest_fuzz_outputs_dirn}")
        
        return True

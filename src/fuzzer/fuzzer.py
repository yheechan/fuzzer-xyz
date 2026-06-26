import signal
import logging
import sys
import shutil
import subprocess

from abc import ABC, abstractmethod
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from src.utils.constants import (
    PACKAGE_MAP,
    PROJ_ROOT,
    INIT_SEED_MAP,
    SUBJECT_ARGV
)
from src.compiler.build_logics import (
    BUILD_LOGICS_MAP
)
from src.coverage.coverage import Coverage

class Fuzzer(ABC):
    output_dir: Path
    target_program: str
    experiment_name: str
    NUM_FUZZERS: int
    fuzz_id: str

    CC: str
    CXX: str
    FUZZER: str
    
    build_logic: callable
    fuzz_id: str

    processes = []
    stop_requested = False

    coverage: Coverage

    def __init__(
            self,
            output_dir: Path,
            target_program: str,
            experiment_name: str = None,
            NUM_FUZZERS: int = 4,
            fuzz_id: str = None
        ):
        self.output_dir = output_dir
        self.target_program = target_program
        self.NUM_FUZZERS = NUM_FUZZERS
        self.fuzz_id = fuzz_id
        self.experiment_name = experiment_name

        self.package_name = PACKAGE_MAP[target_program]
        self.build_logic = BUILD_LOGICS_MAP[self.package_name]


    def __str__(self) -> str:
        return self.__class__.__name__
    
    @abstractmethod
    def compile(self) -> bool:
        raise NotImplementedError("Subclasses must implement the compile method.")

    @abstractmethod
    def check_fuzz_targets(self) -> bool:
        raise NotImplementedError("Subclasses must implement the check_fuzz_targets method.")

    @abstractmethod
    def wait_print_fuzz_stats(self):
        raise NotImplementedError("Subclasses must implement the wait_print_fuzz_stats method.")
    
    @abstractmethod
    def fuzz(self) -> bool:
        raise NotImplementedError("Subclasses must implement the fuzz method.")

    @abstractmethod
    def targets_on_server(self, server_address: str) -> bool:
        raise NotImplementedError("Subclasses must implement the targets_on_server method.")

    @abstractmethod
    def init_coverage(self) -> bool:
        raise NotImplementedError("Subclasses must implement the init_coverage method.")

    @abstractmethod
    def read_plot_data(plot_data_fn: Path) -> list[tuple[int, int]]:
        raise NotImplementedError("Subclasses must implement the read_plot_data method.")
      
    def init_fuzz_output_dir(self) -> bool:
        self.experiment_dirn = self.output_dir / "baseline_fuzzing" / self.__class__.__name__ / self.experiment_name
        self.experiment_dirn.mkdir(parents=True, exist_ok=True)

        self.outputs_dirn = self.experiment_dirn / "fuzz_outputs"
        self.outputs_dirn.mkdir(parents=True, exist_ok=True)

        self.logs_dirn = self.experiment_dirn / "logs"
        self.logs_dirn.mkdir(parents=True, exist_ok=True)

        self.coverage_dirn = self.experiment_dirn / "coverage"
        self.coverage_dirn.mkdir(parents=True, exist_ok=True)

        return True
    
    def init_fuzz_logger(self) -> bool:
        log_file = self.logs_dirn / f"{self.fuzz_id}.fuzzing.log"
        logging.basicConfig(
            level=logging.INFO,
            format="[%(asctime)s] %(levelname)s: %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
            handlers=[
                logging.FileHandler(log_file, mode='w'),
                logging.StreamHandler(sys.stdout)
            ]
        )
        self.logger = logging.getLogger(__name__)
        return True
    
    def set_general_requirements(self) -> bool:
        # Check if the required tools are available in PATH
        for tool in [self.CC, self.CXX, self.FUZZER, "llvm-config", "llvm-cov", "opt", "clang", "clang++"]:
            if not shutil.which(tool):
                self.logger.error(f"Required tool '{tool}' not found in PATH.")
                return False
        
        self.init_seed_dirn = PROJ_ROOT / "data" / "init_seeds" / INIT_SEED_MAP[self.target_program]
        if not self.init_seed_dirn.exists():
            self.logger.error(f"Initial seed directory does not exist: {self.init_seed_dirn}")
            return False
        
        self.subject_argv = SUBJECT_ARGV[self.target_program]

        return True
    
    
    def handle_sigint(self, signum, frame):
        if self.stop_requested:
            return

        self.stop_requested = True
        self.logger.info("Received SIGINT, terminating fuzzers...")

        for p in self.processes:
            if p.poll() is None:
                p.send_signal(signal.SIGINT)
    
    
    def send_fuzz_targets_to_server(self, server_address: str) -> bool:

        # Make sure the output directory exists on the server
        cmd = f"ssh {server_address} 'mkdir -p {self.output_dir}'"
        result = subprocess.run(
            cmd,
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        if result.returncode != 0:
            print(f"[MKDIR-ERROR] Failed to create directory on server {server_address}: {result.stderr}")
            return False
        
        # Use SCP to send the fuzzing targets to the server
        for item in self.output_dir.iterdir():
            if item.name == "baseline_fuzzing":
                continue  # Skip the baseline_fuzzing directory itself

            cmd = f"scp -rq {item} {server_address}:{self.output_dir}/"
            result = subprocess.run(
                cmd,
                shell=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            if result.returncode != 0:
                print(f"[SCP-ERROR] Failed to send {item} to server {server_address}: {result.stderr}")
                return False
            else:
                print(f"[SCP-SUCCESS] Successfully sent {item} to server {server_address}")

        return True

    def retrieve_fuzz_results_from_server(self, server_address: str, fuzz_id: str) -> bool:
        # Use SCP to retrieve the fuzzing results from the server
        fuzz_id_output_dir = f"{self.output_dir}/baseline_fuzzing/{self.__class__.__name__}/{self.experiment_name}/fuzz_outputs/{fuzz_id}"
        logfn = f"{self.output_dir}/baseline_fuzzing/{self.__class__.__name__}/{self.experiment_name}/logs/{fuzz_id}.fuzzing.log"

        for fn in [fuzz_id_output_dir, logfn]:
            # check if dir exists locally
            dirn = Path(fn).parent
            if not dirn.exists():
                dirn.mkdir(parents=True, exist_ok=True)
            
        # tar.gz the fuzz_output/fuzz_id directory on the server before retrieving
        fuzz_output_dir = Path(fuzz_id_output_dir).parent

        cmd = f"ssh {server_address} 'cd {fuzz_output_dir} && tar -czf {fuzz_id}.tar.gz {fuzz_id}'"
        result = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            shell=True
        )
        if result.returncode != 0:
            print(f"[TAR-ERROR] Failed to tar {fuzz_output_dir} on server {server_address}: {result.stderr}")
            return False
    
        # Now retrieve the tar.gz file
        tar_fn = f"{fuzz_output_dir}/{fuzz_id}.tar.gz"
        
        cmd = f"scp -rq {server_address}:{tar_fn} {fuzz_output_dir}/"
        result = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            shell=True,
            text=True
        )
        if result.returncode != 0:
            print(f"[RETRIEVE-ERROR] Failed to retrieve {tar_fn} from server {server_address}: {result.stderr}")
            return False
        
        # Now retrieve logfn
        log_dirn = Path(logfn).parent

        cmd = f"scp -rq {server_address}:{logfn} {log_dirn}/"
        result = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            shell=True,
            text=True
        )
        if result.returncode != 0:
            print(f"[RETRIEVE-ERROR] Failed to retrieve {logfn} from server {server_address}: {result.stderr}")
            return False
        
        return True

    def coverage_targets_on_server(self, server_address: str) -> bool:
        baseline_build_dirp = self.output_dir / "drivers" / "baseline_build"
        system_drivers_dirp = self.output_dir / "drivers" / "system_drivers"

        gcov_fp = baseline_build_dirp / "install" / "bin" / self.target_program
        bbcov_fp = system_drivers_dirp / f"{self.target_program}.cov"

        targets = [gcov_fp, bbcov_fp]
        for target in targets:
            cmd = f"ssh {server_address} 'ls {target}'"
            result = subprocess.run(
                cmd,
                shell=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            result_str = result.stderr.decode().strip()
            on_server = False if "No such file or directory" in result_str else True
            if not on_server:
                return False

        return True

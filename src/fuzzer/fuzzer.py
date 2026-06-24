import signal
import logging
import sys
import shutil

from abc import ABC, abstractmethod
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from src.utils.constants import (
    PROJ_ROOT,
    INIT_SEED_MAP,
    SUBJECT_ARGV
)

class Fuzzer(ABC):
    output_dir: Path
    target_program: str

    CC: str
    CXX: str
    FUZZER: str
    build_logic: callable
    fuzz_id: str

    processes = []
    stop_requested = False

    def __init__(
            self,
            output_dir: Path,
            target_program: str,
            experiment_name: str = None,
            fuzz_id: str = None
        ):
        self.output_dir = output_dir
        self.target_program = target_program
        self.experiment_name = experiment_name
        self.fuzz_id = fuzz_id

    def __str__(self) -> str:
        return self.__class__.__name__
    
    def compile(self) -> bool:
        print(f"Building {self.target_program} with {self.__class__.__name__}...")
        success = self.build_logic(self.output_dir / "drivers" / "orig_build")
        if not success:
            print(f"Failed to build {self.target_program} with {self.__class__.__name__}")
            return False
        print(f"Successfully built {self.target_program} with {self.__class__.__name__}")
        return True
      
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
        for tool in [self.CC, self.CXX, self.FUZZER, "llvm-config"]:
            if not shutil.which(tool):
                self.logger.error(f"Required tool '{tool}' not found in PATH.")
                return False
        
        self.init_seed_dirn = PROJ_ROOT / "data" / "init_seeds" / INIT_SEED_MAP[self.target_program]
        if not self.init_seed_dirn.exists():
            self.logger.error(f"Initial seed directory does not exist: {self.init_seed_dirn}")
            return False
        
        self.subject_argv = SUBJECT_ARGV[self.target_program]

        return True
    
    @abstractmethod
    def check_fuzz_targets(self) -> bool:
        raise NotImplementedError("Subclasses must implement the check_fuzz_targets method.")
    
    def handle_sigint(self, signum, frame):
        if self.stop_requested:
            return

        self.stop_requested = True
        self.logger.info("Received SIGINT, terminating fuzzers...")

        for p in self.processes:
            if p.poll() is None:
                p.send_signal(signal.SIGINT)
    
    @abstractmethod
    def wait_print_fuzz_stats(self):
        raise NotImplementedError("Subclasses must implement the wait_print_fuzz_stats method.")
    
    @abstractmethod
    def fuzz(self) -> bool:
        raise NotImplementedError("Subclasses must implement the fuzz method.")

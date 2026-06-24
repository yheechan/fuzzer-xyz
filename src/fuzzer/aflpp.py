import sys

from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from src.utils.constants import (
    AFL_CC,
    AFL_CXX,
    AFL_FUZZER,
)
from src.fuzzer.fuzzer import Fuzzer

class AFLppFuzzer(Fuzzer):
    def __init__(
            self,
            output_dir: Path,
            target_program: str,
            experiment_name: str = None,
            NUM_FUZZERS: int = 4,
            fuzz_id: str = None
        ):
        super().__init__(output_dir, target_program, experiment_name, NUM_FUZZERS, fuzz_id)
        self.CC = str(AFL_CC)
        self.CXX = str(AFL_CXX)
        self.FUZZER = str(AFL_FUZZER)

    def compile(self) -> bool:
        # AFL++ does not need builder/: it reuses the whole-program .bc from the
        # compile step to produce <target>.afl with afl-clang. Not implemented yet.
        raise NotImplementedError("Compile for AFL++ is not implemented yet.")

    def check_fuzz_targets(self) -> bool:
        raise NotImplementedError("Check fuzz targets for AFL++ is not implemented yet.")

    def wait_print_fuzz_stats(self):
        raise NotImplementedError("Wait and print fuzz stats for AFL++ is not implemented yet.")

    def fuzz(self) -> bool:
        raise NotImplementedError("Fuzzing logic for AFL++ is not implemented yet.")

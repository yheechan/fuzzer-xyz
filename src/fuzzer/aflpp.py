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
    
    def targets_on_server(self, server_address: str) -> bool:
        raise NotImplementedError("Check if targets exist on server for AFL++ is not implemented yet.")
    
    def init_coverage(self) -> bool:
        raise NotImplementedError("Initialize coverage for AFL++ is not implemented yet.")

    def read_plot_data(self, plot_data_fn: Path) -> list[tuple[int, int]]:
        """Parse AFL plot_data into a list of (relative_time_sec, corpus_count).

        Columns (per AFL header):
            relative_time, cycles_done, cur_item, corpus_count, ...
        so index 0 is relative_time (seconds) and index 3 is corpus_count. Comment
        and malformed lines are skipped. Samples are returned in chronological order;
        corpus_count is monotonically non-decreasing.
        """
        samples: list[tuple[int, int]] = []
        with open(plot_data_fn) as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                cols = [c.strip() for c in line.split(",")]
                if len(cols) <= 3:
                    continue
                try:
                    rel_time = int(float(cols[0]))
                    corpus_count = int(cols[3])
                except ValueError:
                    continue
                samples.append((rel_time, corpus_count))
        return samples


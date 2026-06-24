import sys

from typing import Dict, Type
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from src.fuzzer.fuzzer import Fuzzer
from src.fuzzer.aflpp import AFLppFuzzer
from src.fuzzer.angora import AngoraFuzzer

class FuzzerFactory:
    fuzzers: Dict[str, Type[Fuzzer]] = {
        "aflpp": AFLppFuzzer,
        "angora": AngoraFuzzer,
    }

    @classmethod
    def create_fuzzer(
        cls,
        output_dir: Path,
        target_program: str,
        fuzzer_name: str,
        experiment_name: str = None,
        NUM_FUZZERS: int = 4,
        fuzz_id: str = None
    ) -> Fuzzer:
        if fuzzer_name not in cls.fuzzers:
            raise ValueError(f"Unknown fuzzer: {fuzzer_name}")
        return cls.fuzzers[fuzzer_name](
            output_dir,
            target_program,
            experiment_name,
            NUM_FUZZERS,
            fuzz_id
        )

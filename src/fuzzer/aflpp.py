import sys

from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from src.utils.constants import (
    PACKAGE_MAP
)
from src.fuzzer.fuzzer import Fuzzer
from src.utils.constants import (
    AFL_CC,
    AFL_CXX,
    AFL_FUZZER,
)

from src.builder.aflpp_builder import BUILD_LOGICS_MAP
    
class AFLppFuzzer(Fuzzer):
    def __init__(self, output_dir: Path, target_program: str):
        super().__init__(output_dir, target_program)
        self.CC = str(AFL_CC)
        self.CXX = str(AFL_CXX)
        self.FUZZER = str(AFL_FUZZER)
        self.package_name = PACKAGE_MAP[target_program]
        self.build_logic = BUILD_LOGICS_MAP[self.package_name]

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
    ANGORA_CC,
    ANGORA_CXX,
    ANGORA_FUZZER,
)

from src.builder.angora_builder import BUILD_LOGICS_MAP

class AngoraFuzzer(Fuzzer):
    def __init__(self, output_dir: Path, target_program: str):
        super().__init__(output_dir, target_program)
        self.CC = str(ANGORA_CC)
        self.CXX = str(ANGORA_CXX)
        self.FUZZER = str(ANGORA_FUZZER)
        self.package_name = PACKAGE_MAP[target_program]
        self.build_logic = BUILD_LOGICS_MAP[self.package_name]

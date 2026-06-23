

from abc import ABC, abstractmethod
from pathlib import Path


class Fuzzer(ABC):
    output_dir: Path
    target_program: str

    CC: str
    CXX: str
    FUZZER: str
    build_logic: callable

    def __init__(self, output_dir: Path, target_program: str):
        self.output_dir = output_dir
        self.target_program = target_program
        self.build_logic = None

    def compile(self) -> bool:
        print(f"Building {self.target_program} with {self.__class__.__name__}...")
        success = self.build_logic(self.output_dir / "drivers" / "orig_build")
        if not success:
            print(f"Failed to build {self.target_program} with {self.__class__.__name__}")
            return False
        print(f"Successfully built {self.target_program} with {self.__class__.__name__}")
        return True

    def __str__(self) -> str:
        return self.__class__.__name__

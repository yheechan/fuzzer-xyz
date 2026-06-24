from enum import Enum
from pathlib import Path

PROJ_ROOT = Path(__file__).resolve().parent.parent.parent

AFL_ROOT = PROJ_ROOT / "AFLplusplus"
AFL_CC = AFL_ROOT / "afl-clang-lto"
AFL_CXX = AFL_ROOT / "afl-clang-lto++"
AFL_FUZZER = AFL_ROOT / "afl-fuzz"

ANGORA_ROOT = PROJ_ROOT / "Angora"
ANGORA_CC = ANGORA_ROOT / "bin" / "angora-clang"
ANGORA_CXX = ANGORA_ROOT / "bin" / "angora-clang++"
ANGORA_FUZZER = ANGORA_ROOT / "bin" / "fuzzer"

BB_COV_DIR = PROJ_ROOT / "bb_cov"
BB_COV_BUILD = BB_COV_DIR / "build"

BASELINE_FUZZERS = [
    "aflpp",
    "angora",
]

TARGET_SUBJECTS = [
    "avconv",
    "bison",
    "cjpeg",
    "dwarfdump",
    "exiv2",
    "ffmpeg",
    "gm",
    "gs",
    "jasper",
    "mpg123",
    "nasm",
    "objdump",
    "pdftohtml",
    "pdftopng",
    "pspp",
    "readelf",
    "tiff2pdf",
    "tiff2ps",
    "xmllint",
    "xmlwf"
]


class PassEnum(str, Enum):
    SA_PASS = "static_analysis_pass.so"
    UNIT_DRIVER_PASS = "unit_driver_pass.so"
    EXTRACTOR_PASS = "extractor_pass.so"
    BB_COV_PASS = "bb_cov_pass.so"
    PATH_COV_PASS = "path_cov_pass.so"

    @classmethod
    def to_dict(cls):
        return {item.name: item.value for item in cls}


PASS_OPTIONS = {
    PassEnum.SA_PASS: "--passes=sa",
    PassEnum.UNIT_DRIVER_PASS: "--passes=unit_driver",
    PassEnum.EXTRACTOR_PASS: "--passes=extractor",
    PassEnum.BB_COV_PASS: "--passes=bbcov",
    PassEnum.PATH_COV_PASS: "--passes=pathcov",
}

PASS_DIRS = {
    PassEnum.BB_COV_PASS: BB_COV_BUILD,
    PassEnum.PATH_COV_PASS: BB_COV_BUILD,
}


# constants that should be read before running the experiment
class ExperimentSetup:
    def __init__(
        self,
        subject_root: str,  # root directory containing subject programs
        api_keys: dict,  # API keys for LLMs
    ):
        self.subject_root = subject_root
        self.api_keys = api_keys


experiment_setup = None


# Read JSON files in data/base_data and .machines.json, .constant.json
def read_experiment_setup() -> None:
    global experiment_setup

    # constant_fn = PROJ_ROOT / ".constant.json"
    # if not constant_fn.exists():
    #     raise FileNotFoundError(f"Constant JSON file not found at {constant_fn}")

    # with open(constant_fn, "r") as f:
    #     constant = json.load(f)

    # if "SUBJECT_ROOT" not in constant:
    #     raise KeyError(f"'SUBJECT_ROOT' key not found in {constant_fn}")

    # subject_root = Path(constant["SUBJECT_ROOT"]).absolute()

    # if not subject_root.exists():
    #     raise FileNotFoundError(f"Subject root directory not found at {subject_root}")

    # api_keys = constant.get("API_KEYS", {})

    # experiment_setup = ExperimentSetup(
    #     subject_root,
    #     api_keys,
    # )

    return


read_experiment_setup()


def get_experiment_setup() -> ExperimentSetup:
    return experiment_setup


PACKAGE_MAP = {
    "avconv": "libav",
    "bison": "bison",
    "cjpeg": "libjpeg-turbo",
    "dwarfdump": "libdwarf",
    "exiv2": "exiv2",
    "ffmpeg": "ffmpeg",
    "gm": "GraphicsMagick",
    "gs": "ghostpdl",
    "jasper": "jasper",
    "mpg123": "mpg123",
    "nasm": "nasm",
    "objdump": "binutils",
    "pdftohtml": "poppler",
    "pdftopng": "xpdf",
    "pspp": "pspp",
    "readelf": "binutils",
    "tiff2pdf": "libtiff",
    "tiff2ps": "libtiff",
    "xmllint": "libxml2",
    "xmlwf": "expat"
}

## The subject program should only read the "@@" file as input.
## The program should not write to the "@@" file.
SUBJECT_ARGV = {
    "avconv": ["-i", "@@", "-r", "24", "tmp.avi"],
    "bison": ["@@", "-o", "/dev/null"],
    "cjpeg": ["@@"],
    "dwarfdump": ["-b", "-a", "-r", "-f", "-i", "-ls", "-c", "-ta", "@@"],
    "exiv2": ["@@"],
    "ffmpeg": ["-i", "@@", "-f", "mp4", "-y", "/dev/null"],
    "gm": ["identify", "@@"],
    "gs": ["-sDEVICE=pdfwrite", "-o", "/dev/null", "@@"],
    "jasper": ["-f", "@@", "-T", "bmp", "-F", "/dev/null"],
    "mpg123": ["-w", "/dev/null", "@@"],
    "nasm": ["@@", "-o", "/dev/null"],
    "objdump": ["-d", "@@"],
    "pdftohtml": ["@@"],
    "pdftopng": ["@@", "/dev/null"],
    "pspp": ["-o", "/dev/null", "-O", "format=odt", "@@"],
    "readelf": ["-a", "@@"],
    "tiff2pdf": ["@@", "-o", "/dev/null"],
    "tiff2ps": ["@@"],
    "xmllint": ["@@"],
    "xmlwf": ["@@"]
}
INIT_SEED_MAP = {
    "avconv": "avi",
    "bison": "y",
    "cjpeg": "jpg",
    "dwarfdump": "dwarf",
    "exiv2": "exi",
    "ffmpeg": "wav",
    "gm": "jpg",
    "gs": "ps",
    "jasper": "jpg",
    "mpg123": "mpg",
    "nasm": "asm",
    "objdump": "elf",
    "pdftohtml": "pdf",
    "pdftopng": "pdf",
    "pspp": "sav",
    "readelf": "elf",
    "tiff2pdf": "tif",
    "tiff2ps": "tif",
    "xmllint": "xml",
    "xmlwf": "exp"
}
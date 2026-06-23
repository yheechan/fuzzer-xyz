import os
import re
import shutil
import subprocess
from pathlib import Path

from src.utils.constants import (
    AFL_CC,
)

BUILD_LOGICS_MAP = {
    # "libav": build_libav,
    # "bison": build_bison,
    # "libjpeg-turbo": build_libjpeg_turbo,
    # "libdwarf": build_libdwarf,
    # "exiv2": build_exiv2,
    # "ffmpeg": build_ffmpeg,
    # "GraphicsMagick": build_GraphicsMagick,
    # "ghostpdl": build_ghostpdl,
    # "jasper": build_jasper,
    # "mpg123": build_mpg123,
    # "nasm": build_nasm,
    # "binutils": build_binutils,
    # "poppler": build_poppler,
    # "xpdf": build_xpdf,
    # "pspp": build_pspp,
    # "libtiff": build_libtiff,
    # "libxml2": build_libxml2,
    # "expat": build_expat,
}

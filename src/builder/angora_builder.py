import os
import re
import shutil
import subprocess
from pathlib import Path

from src.utils.constants import (
    PROJ_ROOT,
    ANGORA_CC,
    ANGORA_ROOT,
)

from src.utils.configs import (
    LLVM12_ROOT,
)

# External taint-source model for open64(), kept here so the Angora submodule
# stays pristine. open64_rule.c is committed; the .o is compiled on demand.
ANGORA_RULES_DIR = PROJ_ROOT / "data" / "angora_rules"


def _angora_env(
    extra_rule_list: Path | None = None,
    custom_rule_obj: Path | None = None,
) -> dict:
    """Environment that makes `angora-clang` use the LLVM 12 backend its
    prebuilt passes require (the system clang is 20.x and is incompatible).

    - PATH / LD_LIBRARY_PATH expose the llvm-12 toolchain plus Angora's
      libruntime.a / libruntime_fast.a (under Angora/bin/lib).
    - ANGORA_CC / ANGORA_CXX select the next-stage compiler (clang-12).
    - ANGORA_TAINT_RULE_LIST, when given, supplies an extra DFSan abilist
      (external libs marked uninstrumented, plus open64=custom).
    - ANGORA_TAINT_CUSTOM_RULE, when given, is an object file linked into the
      track binary that defines extra __dfsw_* wrappers (here: __dfsw_open64).
    """
    env = os.environ.copy()
    llvm_bin = str(LLVM12_ROOT / "bin")
    ld_paths = [
        str(ANGORA_ROOT / "bin" / "lib"),
        str(LLVM12_ROOT / "lib"),
    ]
    env["PATH"] = llvm_bin + os.pathsep + env.get("PATH", "")
    env["LD_LIBRARY_PATH"] = os.pathsep.join(
        ld_paths + ([env["LD_LIBRARY_PATH"]] if env.get("LD_LIBRARY_PATH") else [])
    )
    env["ANGORA_CC"] = str(LLVM12_ROOT / "bin" / "clang")
    env["ANGORA_CXX"] = str(LLVM12_ROOT / "bin" / "clang++")
    if extra_rule_list is not None:
        env["ANGORA_TAINT_RULE_LIST"] = str(extra_rule_list)
    if custom_rule_obj is not None:
        env["ANGORA_TAINT_CUSTOM_RULE"] = str(custom_rule_obj)
    return env


def _ensure_open64_rule_obj() -> Path | None:
    """Compile the external open64 taint-source wrapper to an object file.

    libav/ffmpeg are built with -D_FILE_OFFSET_BITS=64, so they call open64
    instead of open. Angora's bundled io_func.c only models open, so the input
    fd is never tainted and the track run yields zero constraints. Routing
    open64 to this wrapper (via ANGORA_TAINT_RULE_LIST + ANGORA_TAINT_CUSTOM_RULE)
    fixes it without modifying the Angora submodule.
    """
    src = ANGORA_RULES_DIR / "open64_rule.c"
    obj = ANGORA_RULES_DIR / "open64_rule.o"
    if not src.exists():
        print(f"Missing open64 taint-source model: {src}")
        return None
    res = subprocess.run(
        [str(LLVM12_ROOT / "bin" / "clang"), "-c", "-fPIC", "-O2", str(src), "-o", str(obj)],
    )
    if res.returncode != 0 or not obj.exists():
        print("Failed to compile open64_rule.o")
        return None
    return obj

def _gen_dfsan_abilist(out_fn: Path) -> bool:
    """Generate a DFSan abilist that marks zlib + bzip2 as uninstrumented.

    Without this, Angora's USE_TRACK (DFSan) build rewrites calls such as
    inflate/deflate/uncompress/BZ2_bzDecompress* into `dfs$<fn>` and fails to
    link, because those system libraries are not instrumented. The gen tool
    emits versioned symbols (e.g. `deflateBound@@ZLIB_1.2.0`); DFSan matches
    plain names, so we strip the `@@VERSION` suffixes.
    """
    gen_tool = ANGORA_ROOT / "tools" / "gen_library_abilist.sh"

    def realpath_lib(soname: str) -> str | None:
        # pick the concrete versioned .so (e.g. libz.so.1.3) so nm sees symbols
        candidates = sorted(Path("/usr/lib/x86_64-linux-gnu").glob(soname + ".*"))
        candidates = [c for c in candidates if not c.is_symlink()]
        return str(candidates[-1]) if candidates else None

    libs = [realpath_lib("libz.so"), realpath_lib("libbz2.so")]
    libs = [l for l in libs if l]
    if not libs:
        print("Could not locate libz/libbz2 to generate DFSan abilist")
        return False

    raw = ""
    for lib in libs:
        res = subprocess.run(
            ["sh", str(gen_tool), lib, "discard"],
            capture_output=True, text=True,
        )
        raw += res.stdout

    # strip @@VERSION tags and dedup so plain function names are matched
    lines = set()
    for line in raw.splitlines():
        lines.add(re.sub(r"@@[A-Za-z0-9._]+=", "=", line))
    out_fn.write_text("\n".join(sorted(lines)) + "\n")
    return True

def build_libav(work_dir: Path) -> bool:
    src_dir = work_dir / "libav-12.3"

    if not src_dir.exists():
        print(f"Source directory {src_dir} does not exist after extraction")
        return False

    os.chdir(src_dir)

    install_dir = work_dir / "install"

    # libav is built with Angora's instrumenting compiler into two binaries:
    # a USE_TRACK (DFSan taint) copy saved as `*.taint`, and a USE_FAST (light
    # instrumentation) copy saved as `*.fast`, as required by angora_fuzzer.
    # The env points angora-clang at its required LLVM-12 backend.
    abilist_fn = work_dir / "angora_extra_abilist.txt"
    if not _gen_dfsan_abilist(abilist_fn):
        return False
    # Route open64 to our external __dfsw_open64 wrapper (keeps Angora pristine).
    with abilist_fn.open("a") as f:
        f.write("fun:open64=custom\n")
    open64_obj = _ensure_open64_rule_obj()
    if open64_obj is None:
        return False
    env = _angora_env(extra_rule_list=abilist_fn, custom_rule_obj=open64_obj)

    # libav's configure is pure C: it uses --cc/--ld and has no --cxx option.
    extra_cflags = "-g -O0 -Wno-error=incompatible-function-pointer-types"

    cmd = [
        "./configure",
        f"--cc={ANGORA_CC}",
        f"--ld={ANGORA_CC}",
        f"--extra-cflags={extra_cflags}",
        f"--prefix={install_dir}",
        "--disable-doc",
        "--disable-asm",
        "--enable-debug",
    ]

    subprocess.run(cmd, env=env)

    drivers_dir = work_dir.parent
    system_drivers_dir = drivers_dir / "system_drivers"

    # Track build (DFSan taint tracking) -> save the target binaries as *.taint
    subprocess.run(["make", "clean"], env=env)
    subprocess.run(["make", "-j", "24"], env={**env, "USE_TRACK": "1"})
    subprocess.run(["make", "install"], env=env)
    for prog in ("avconv", "avprobe"):
        if (install_dir / "bin" / prog).exists():
            shutil.copy(install_dir / "bin" / prog, system_drivers_dir / f"{prog}.taint")

    # make clean is mandatory between modes: otherwise USE_FAST relinks the
    # USE_TRACK object files instead of rebuilding with light instrumentation.
    subprocess.run(["make", "clean"], env=env)
    subprocess.run(["make", "-j", "24"], env={**env, "USE_FAST": "1"})
    subprocess.run(["make", "install"], env=env)
    for prog in ("avconv", "avprobe"):
        if (install_dir / "bin" / prog).exists():
            shutil.copy(install_dir / "bin" / prog, system_drivers_dir / f"{prog}.fast")

    return True


BUILD_LOGICS_MAP = {
    "libav": build_libav,
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

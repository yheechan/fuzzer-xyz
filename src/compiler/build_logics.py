import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from src.utils.constants import PROJ_ROOT


def build_libav(work_dir: Path, for_baseline_fuzz: bool=False) -> bool:
    # 1. copy source code
    src_fn = PROJ_ROOT / "data" / "subjects" / "libav-12.3.tar.gz"
    dest_fn = work_dir / "libav-12.3.tar.gz"
    if not src_fn.exists():
        print(f"Source file {src_fn} does not exist")
        return False

    shutil.copy(src_fn, dest_fn)

    # 2. extract source code()
    shutil.unpack_archive(dest_fn, work_dir)
    src_dir = work_dir / "libav-12.3"

    if not src_dir.exists():
        print(f"Source directory {src_dir} does not exist after extraction")
        return False

    os.chdir(src_dir)

    install_dir = work_dir / "install"

    # For baseline coverage builds we need gcov instrumentation on both the
    # compile step (--coverage emits .gcno) and the link step. ffmpeg-style
    # configure links via its own driver, so pass --extra-ldflags=--coverage too.
    extra_cflags = "-g -O0"
    if for_baseline_fuzz:
        extra_cflags += " --coverage -fno-inline"
    extra_cflags += " -Wno-error=incompatible-function-pointer-types"

    cmd = [
        "./configure",
        "cc=gclang",
        f"--extra-cflags={extra_cflags}",
        f"--prefix={install_dir}",
        "--disable-doc",
        "--disable-asm",
        "--enable-debug",
    ]
    if for_baseline_fuzz:
        cmd.append("--extra-ldflags=--coverage")
    subprocess.run(cmd)

    cmd = ["make", "-j", "24"]
    subprocess.run(cmd)

    cmd = ["make", "install"]
    subprocess.run(cmd)

    return True


def build_bison(work_dir: Path, for_baseline_fuzz: bool=False) -> bool:
    # 1. copy source code
    src_fn = PROJ_ROOT / "data" / "subjects" / "bison-3.8.2.tar.gz"
    dest_fn = work_dir / "bison-3.8.2.tar.gz"
    if not src_fn.exists():
        print(f"Source file {src_fn} does not exist")
        return False

    shutil.copy(src_fn, dest_fn)

    # 2. extract source code()
    shutil.unpack_archive(dest_fn, work_dir)
    src_dir = work_dir / "bison-3.8.2"

    if not src_dir.exists():
        print(f"Source directory {src_dir} does not exist after extraction")
        return False

    os.chdir(src_dir)

    install_dir = work_dir / "install"

    # For baseline coverage builds we need gcov instrumentation on both the
    # compile step (--coverage emits .gcno) and the link step. With autotools,
    # CFLAGS isn't guaranteed to reach the linker, so pass LDFLAGS=--coverage too.
    compiler_flags = "-g -O0"
    if for_baseline_fuzz:
        compiler_flags += " --coverage -fno-inline"

    cmd = [
        "./configure",
        "CC=gclang",
        "CXX=gclang++",
        f"--prefix={install_dir}",
        f"CFLAGS={compiler_flags}",
        f"CXXFLAGS={compiler_flags}",
    ]
    if for_baseline_fuzz:
        cmd.append("LDFLAGS=--coverage")
    subprocess.run(cmd)

    cmd = ["make", "-j", "24"]
    subprocess.run(cmd)

    cmd = ["make", "install"]
    subprocess.run(cmd)

    return True


def build_libjpeg_turbo(work_dir: Path, for_baseline_fuzz: bool=False) -> bool:
    # 1. copy source code
    src_fn = PROJ_ROOT / "data" / "subjects" / "libjpeg-turbo-3.1.4.1.tar.gz"
    dest_fn = work_dir / "libjpeg-turbo-3.1.4.1.tar.gz"
    if not src_fn.exists():
        print(f"Source file {src_fn} does not exist")
        return False

    shutil.copy(src_fn, dest_fn)

    # 2. extract source code()
    shutil.unpack_archive(dest_fn, work_dir)
    src_dir = work_dir / "libjpeg-turbo-3.1.4.1"

    if not src_dir.exists():
        print(f"Source directory {src_dir} does not exist after extraction")
        return False

    os.chdir(src_dir)

    install_dir = work_dir / "install"

    # Use a clean build dir so a stale CMake cache can't override our flags
    build_dir = src_dir / "build"
    if build_dir.exists():
        shutil.rmtree(build_dir)
    build_dir.mkdir()
    os.chdir(build_dir)

    # For baseline coverage builds we need gcov instrumentation on both the
    # compile step (--coverage emits .gcno) and the link step (pulls in libgcov).
    compiler_flags = "-g -O0"
    if for_baseline_fuzz:
        compiler_flags += " --coverage -fno-inline"

    cmd = [
        "cmake",
        "..",
        "-DCMAKE_C_COMPILER=gclang",
        f"-DCMAKE_INSTALL_PREFIX={install_dir}",
        "-DCMAKE_BUILD_TYPE=Debug",
        "-DENABLE_SHARED=OFF",
        "-DENABLE_STATIC=ON",
        "-DWITH_SIMD=OFF",
        "-DWITH_TESTS=OFF",
        "-DWITH_TURBOJPEG=OFF",
        f"-DCMAKE_C_FLAGS={compiler_flags}",
    ]
    if for_baseline_fuzz:
        # Executables are static (ENABLE_SHARED=OFF), so EXE linker flags are
        # what matter; SHARED kept harmless in case shared is re-enabled.
        cmd.append("-DCMAKE_EXE_LINKER_FLAGS=--coverage")
        cmd.append("-DCMAKE_SHARED_LINKER_FLAGS=--coverage")
    subprocess.run(cmd)

    cmd = ["make", "-j", "24"]
    subprocess.run(cmd)

    cmd = ["make", "install"]
    subprocess.run(cmd)

    return True


def build_libdwarf(work_dir: Path, for_baseline_fuzz: bool=False) -> bool:
    # 1. copy source code
    src_fn = PROJ_ROOT / "data" / "subjects" / "libdwarf-2.3.1.tar.gz"
    dest_fn = work_dir / "libdwarf-2.3.1.tar.gz"
    if not src_fn.exists():
        print(f"Source file {src_fn} does not exist")
        return False

    shutil.copy(src_fn, dest_fn)

    # 2. extract source code()
    shutil.unpack_archive(dest_fn, work_dir)
    src_dir = work_dir / "libdwarf-code-2.3.1"

    if not src_dir.exists():
        print(f"Source directory {src_dir} does not exist after extraction")
        return False

    os.chdir(src_dir)

    install_dir = work_dir / "install"

    # Use a clean build dir so a stale CMake cache can't override our flags
    build_dir = src_dir / "build"
    if build_dir.exists():
        shutil.rmtree(build_dir)
    build_dir.mkdir()
    os.chdir(build_dir)

    # For baseline coverage builds we need gcov instrumentation on both the
    # compile step (--coverage emits .gcno) and the link step (pulls in libgcov).
    compiler_flags = "-g -O0"
    if for_baseline_fuzz:
        compiler_flags += " --coverage -fno-inline"

    cmd = [
        "cmake",
        "..",
        "-DCMAKE_C_COMPILER=gclang",
        "-DCMAKE_CXX_COMPILER=gclang++",
        f"-DCMAKE_INSTALL_PREFIX={install_dir}",
        "-DCMAKE_BUILD_TYPE=Debug",
        f"-DCMAKE_C_FLAGS={compiler_flags}",
        f"-DCMAKE_CXX_FLAGS={compiler_flags}",
    ]
    if for_baseline_fuzz:
        cmd.append("-DCMAKE_EXE_LINKER_FLAGS=--coverage")
        cmd.append("-DCMAKE_SHARED_LINKER_FLAGS=--coverage")
    subprocess.run(cmd)

    cmd = ["make", "-j", "24"]
    subprocess.run(cmd)

    cmd = ["make", "install"]
    subprocess.run(cmd)

    return True


def build_exiv2(work_dir: Path, for_baseline_fuzz: bool=False) -> bool:
    # 1. copy source code
    src_fn = PROJ_ROOT / "data" / "subjects" / "exiv2-0.28.8.tar.gz"
    dest_fn = work_dir / "exiv2-0.28.8.tar.gz"
    if not src_fn.exists():
        print(f"Source file {src_fn} does not exist")
        return False

    shutil.copy(src_fn, dest_fn)

    # 2. extract source code()
    shutil.unpack_archive(dest_fn, work_dir)
    src_dir = work_dir / "exiv2-0.28.8"

    if not src_dir.exists():
        print(f"Source directory {src_dir} does not exist after extraction")
        return False

    os.chdir(src_dir)

    install_dir = work_dir / "install"

    # Use a clean build dir so a stale CMake cache can't override our flags
    build_dir = src_dir / "build"
    if build_dir.exists():
        shutil.rmtree(build_dir)
    build_dir.mkdir()
    os.chdir(build_dir)

    compiler_flags = "-g -O0"
    if for_baseline_fuzz:
        compiler_flags += " -fno-inline"

    cmd = [
        "cmake",
        "..",
        "-DCMAKE_C_COMPILER=gclang",
        "-DCMAKE_CXX_COMPILER=gclang++",
        f"-DCMAKE_INSTALL_PREFIX={install_dir}",
        "-DCMAKE_BUILD_TYPE=Debug",
        f"-DCMAKE_C_FLAGS={compiler_flags}",
        f"-DCMAKE_CXX_FLAGS={compiler_flags}",
        "-DBUILD_SHARED_LIBS=OFF",
        "-DEXIV2_BUILD_DOC=OFF",
        "-DEXIV2_BUILD_UNIT_TESTS=OFF",
        "-DEXIV2_BUILD_SAMPLES=OFF",
    ]
    if for_baseline_fuzz:
        # exiv2 has its own coverage option that adds --coverage to both the
        # compile step (.gcno) and the EXE/SHARED link steps (libgcov), so we
        # don't need to set the linker flags manually.
        cmd.append("-DBUILD_WITH_COVERAGE=ON")
    subprocess.run(cmd)

    cmd = ["make", "-j", "24"]
    subprocess.run(cmd)

    cmd = ["make", "install"]
    subprocess.run(cmd)

    return True


def build_ffmpeg(work_dir: Path, for_baseline_fuzz: bool=False) -> bool:
    # 1. copy source code
    src_fn = PROJ_ROOT / "data" / "subjects" / "ffmpeg-8.1.1.tar.xz"
    dest_fn = work_dir / "ffmpeg-8.1.1.tar.xz"
    if not src_fn.exists():
        print(f"Source file {src_fn} does not exist")
        return False

    shutil.copy(src_fn, dest_fn)

    # 2. extract source code()
    shutil.unpack_archive(dest_fn, work_dir)
    src_dir = work_dir / "ffmpeg-8.1.1"

    if not src_dir.exists():
        print(f"Source directory {src_dir} does not exist after extraction")
        return False

    # 3. build and install
    os.chdir(src_dir)

    install_dir = work_dir / "install"

    # For baseline coverage builds we need gcov instrumentation on both the
    # compile step (--coverage emits .gcno) and the link step. ffmpeg-style
    # configure links via its own driver, so pass --extra-ldflags=--coverage too.
    extra_flags = "-g -O0"
    if for_baseline_fuzz:
        extra_flags += " --coverage -fno-inline"

    cmd = [
        "./configure",
        "cc=gclang",
        "cxx=gclang++",
        f"--prefix={install_dir}",
        f"--extra-cflags={extra_flags}",
        f"--extra-cxxflags={extra_flags}",
        "--disable-doc",
        "--disable-asm",
        "--enable-debug",
        "--disable-stripping",
    ]
    if for_baseline_fuzz:
        cmd.append("--extra-ldflags=--coverage")
    subprocess.run(cmd)

    cmd = ["make", "-j", "24"]
    subprocess.run(cmd)

    cmd = ["make", "install"]
    subprocess.run(cmd)

    return True


def build_GraphicsMagick(work_dir: Path, for_baseline_fuzz: bool=False) -> bool:
    # 1. copy source code
    src_fn = PROJ_ROOT / "data" / "subjects" / "GraphicsMagick-1.3.47.tar.xz"
    dest_fn = work_dir / "GraphicsMagick-1.3.47.tar.xz"
    if not src_fn.exists():
        print(f"Source file {src_fn} does not exist")
        return False

    shutil.copy(src_fn, dest_fn)

    # 2. extract source code()
    shutil.unpack_archive(dest_fn, work_dir)
    src_dir = work_dir / "GraphicsMagick-1.3.47"

    if not src_dir.exists():
        print(f"Source directory {src_dir} does not exist after extraction")
        return False

    # 3. build and install
    os.chdir(src_dir)

    install_dir = work_dir / "install"

    # For baseline coverage builds we need gcov instrumentation on both the
    # compile step (--coverage emits .gcno) and the link step. libtool links
    # via the linker driver, so pass LDFLAGS=--coverage too.
    compiler_flags = "-g -O0"
    if for_baseline_fuzz:
        compiler_flags += " --coverage -fno-inline"

    cmd = [
        "./configure",
        "--disable-shared",
        "CC=gclang",
        "CXX=gclang++",
        f"--prefix={install_dir}",
        f"CFLAGS={compiler_flags}",
        f"CXXFLAGS={compiler_flags}",
    ]
    if for_baseline_fuzz:
        cmd.append("LDFLAGS=--coverage")
    subprocess.run(cmd)

    cmd = ["make", "-j", "24"]
    subprocess.run(cmd)

    cmd = ["make", "install"]
    subprocess.run(cmd)

    return True


def build_ghostpdl(work_dir: Path, for_baseline_fuzz: bool=False) -> bool:
    # 1. copy source code
    src_fn = PROJ_ROOT / "data" / "subjects" / "ghostpdl-10.07.1.tar.gz"
    dest_fn = work_dir / "ghostpdl-10.07.1.tar.gz"
    if not src_fn.exists():
        print(f"Source file {src_fn} does not exist")
        return False

    shutil.copy(src_fn, dest_fn)

    # 2. extract source code
    shutil.unpack_archive(dest_fn, work_dir)
    src_dir = work_dir / "ghostpdl-ghostpdl-10.07.1"

    if not src_dir.exists():
        print(f"Source directory {src_dir} does not exist after extraction")
        return False

    # 3. build and install
    os.chdir(src_dir)

    install_dir = work_dir / "install"

    # For baseline coverage builds we need gcov instrumentation on both the
    # compile step (--coverage emits .gcno) and the link step. ghostpdl links
    # via $(CC), so pass LDFLAGS=--coverage too.
    compiler_flags = "-g -O0"
    if for_baseline_fuzz:
        compiler_flags += " --coverage -fno-inline"

    # autogen.sh regenerates configure and forwards these args straight to it.
    cmd = [
        "./autogen.sh",
        "CC=gclang",
        "CXX=gclang++",
        f"--prefix={install_dir}",
        f"CFLAGS={compiler_flags}",
        f"CXXFLAGS={compiler_flags}",
    ]
    if for_baseline_fuzz:
        cmd.append("LDFLAGS=--coverage")
    subprocess.run(cmd)

    cmd = ["make", "-j", "24"]
    subprocess.run(cmd)

    cmd = ["make", "install"]
    subprocess.run(cmd)

    return True


def build_jasper(work_dir: Path, for_baseline_fuzz: bool=False) -> bool:
    # 1. copy source code
    src_fn = PROJ_ROOT / "data" / "subjects" / "jasper-4.2.9.tar.gz"
    dest_fn = work_dir / "jasper-4.2.9.tar.gz"
    if not src_fn.exists():
        print(f"Source file {src_fn} does not exist")
        return False

    shutil.copy(src_fn, dest_fn)

    # 2. extract source code
    shutil.unpack_archive(dest_fn, work_dir)
    src_dir = work_dir / "jasper-4.2.9"

    if not src_dir.exists():
        print(f"Source directory {src_dir} does not exist after extraction")
        return False

    # 3. build and install
    os.chdir(work_dir)

    install_dir = work_dir / "install"

    # jasper forbids in-source builds, so the build dir must live OUTSIDE the
    # source tree (sibling of jasper-4.2.9). Use a clean dir so a stale CMake
    # cache can't override our flags.
    build_dir = work_dir / "build"
    if build_dir.exists():
        shutil.rmtree(build_dir)
    build_dir.mkdir()
    os.chdir(build_dir)

    # For baseline coverage builds we need gcov instrumentation on both the
    # compile step (--coverage emits .gcno) and the link step (pulls in libgcov).
    compiler_flags = "-g -O0"
    if for_baseline_fuzz:
        compiler_flags += " --coverage -fno-inline"

    cmd = [
        "cmake",
        "../jasper-4.2.9",
        "-DCMAKE_C_COMPILER=gclang",
        "-DCMAKE_CXX_COMPILER=gclang++",
        f"-DCMAKE_INSTALL_PREFIX={install_dir}",
        "-DCMAKE_BUILD_TYPE=Debug",
        f"-DCMAKE_C_FLAGS={compiler_flags}",
        f"-DCMAKE_CXX_FLAGS={compiler_flags}",
        "-DJAS_ENABLE_SHARED=OFF",
        "-DJAS_ENABLE_LIBHEIF=OFF",
        "-DJAS_ENABLE_OPENGL=OFF",
        "-DJAS_ENABLE_DOC=OFF",
        "-DJAS_ENABLE_LATEX=OFF",
    ]
    if for_baseline_fuzz:
        # jasper program is static (JAS_ENABLE_SHARED=OFF), so EXE linker flags
        # are what matter; SHARED kept harmless in case shared is re-enabled.
        cmd.append("-DCMAKE_EXE_LINKER_FLAGS=--coverage")
        cmd.append("-DCMAKE_SHARED_LINKER_FLAGS=--coverage")
    subprocess.run(cmd)

    cmd = ["make", "-j", "24"]
    subprocess.run(cmd)

    cmd = ["make", "install"]
    subprocess.run(cmd)

    return True


def build_mpg123(work_dir: Path, for_baseline_fuzz: bool=False) -> bool:
    # 1. copy source code
    src_fn = PROJ_ROOT / "data" / "subjects" / "mpg123-1.33.5.tar.bz2"
    dest_fn = work_dir / "mpg123-1.33.5.tar.bz2"
    if not src_fn.exists():
        print(f"Source file {src_fn} does not exist")
        return False

    shutil.copy(src_fn, dest_fn)

    # 2. extract source code
    shutil.unpack_archive(dest_fn, work_dir)
    src_dir = work_dir / "mpg123-1.33.5"

    if not src_dir.exists():
        print(f"Source directory {src_dir} does not exist after extraction")
        return False

    # 3. build and install
    os.chdir(src_dir)

    install_dir = work_dir / "install"

    # For baseline coverage builds we need gcov instrumentation on both the
    # compile step (--coverage emits .gcno) and the link step. libtool links
    # via the linker driver, so pass LDFLAGS=--coverage too. mpg123 prepends
    # its own -O2/-finline default optflags, but our trailing -O0/-fno-inline
    # win (gcc honors the last conflicting flag), keeping coverage accurate.
    compiler_flags = "-g -O0"
    if for_baseline_fuzz:
        compiler_flags += " --coverage -fno-inline"

    cmd = [
        "./configure",
        "--disable-shared",
        "CC=gclang",
        "CXX=gclang++",
        f"--prefix={install_dir}",
        f"CFLAGS={compiler_flags}",
        f"CXXFLAGS={compiler_flags}",
    ]
    if for_baseline_fuzz:
        cmd.append("LDFLAGS=--coverage")
    subprocess.run(cmd)

    cmd = ["make", "-j", "24"]
    subprocess.run(cmd)

    cmd = ["make", "install"]
    subprocess.run(cmd)

    return True


def build_nasm(work_dir: Path, for_baseline_fuzz: bool=False) -> bool:
    # 1. copy source code
    src_fn = PROJ_ROOT / "data" / "subjects" / "nasm-3.01.tar.gz"
    dest_fn = work_dir / "nasm-3.01.tar.gz"
    if not src_fn.exists():
        print(f"Source file {src_fn} does not exist")
        return False

    shutil.copy(src_fn, dest_fn)

    # 2. extract source code
    shutil.unpack_archive(dest_fn, work_dir)
    src_dir = work_dir / "nasm-3.01"

    if not src_dir.exists():
        print(f"Source directory {src_dir} does not exist after extraction")
        return False

    # 3. build and install
    os.chdir(src_dir)

    install_dir = work_dir / "install"

    # For baseline coverage builds we need gcov instrumentation on both the
    # compile step (--coverage emits .gcno) and the link step. nasm links via
    # $(CC), so pass LDFLAGS=--coverage too. (nasm has no shared lib, so
    # --disable-shared is unnecessary and just warns; omitted.)
    compiler_flags = "-g -O0"
    if for_baseline_fuzz:
        compiler_flags += " --coverage -fno-inline"

    cmd = [
        "./configure",
        "CC=gclang",
        "CXX=gclang++",
        f"--prefix={install_dir}",
        f"CFLAGS={compiler_flags}",
        f"CXXFLAGS={compiler_flags}",
    ]
    if for_baseline_fuzz:
        cmd.append("LDFLAGS=--coverage")
    subprocess.run(cmd)

    cmd = ["make", "-j", "24"]
    subprocess.run(cmd)

    cmd = ["make", "install"]
    subprocess.run(cmd)

    return True


def build_binutils(work_dir: Path, for_baseline_fuzz: bool=False) -> bool:
    # 1. copy source code
    src_fn = PROJ_ROOT / "data" / "subjects" / "binutils-2.46.0.tar.xz"
    dest_fn = work_dir / "binutils-2.46.0.tar.xz"
    if not src_fn.exists():
        print(f"Source file {src_fn} does not exist")
        return False

    shutil.copy(src_fn, dest_fn)

    # 2. extract source code
    shutil.unpack_archive(dest_fn, work_dir)
    src_dir = work_dir / "src"

    if not src_dir.exists():
        print(f"Source directory {src_dir} does not exist after extraction")
        return False

    # 3. build and install
    os.chdir(src_dir)

    install_dir = work_dir / "install"

    # For baseline coverage builds we need gcov instrumentation on both the
    # compile step (--coverage emits .gcno) and the link step. binutils is a
    # multi-component tree; the top-level configure propagates these flags down
    # to every subdir (bfd, opcodes, libiberty, gas, ld, binutils), and links
    # via $(CC), so pass LDFLAGS=--coverage too.
    compiler_flags = "-g -O0"
    if for_baseline_fuzz:
        compiler_flags += " --coverage -fno-inline"

    cmd = [
        "./configure",
        "--disable-shared",
        "CC=gclang",
        "CXX=gclang++",
        f"--prefix={install_dir}",
        f"CFLAGS={compiler_flags}",
        f"CXXFLAGS={compiler_flags}",
    ]
    if for_baseline_fuzz:
        cmd.append("LDFLAGS=--coverage")
    subprocess.run(cmd)

    cmd = ["make", "-j", "24"]
    subprocess.run(cmd)

    cmd = ["make", "install"]
    subprocess.run(cmd)

    return True


def build_poppler(work_dir: Path, for_baseline_fuzz: bool=False) -> bool:
    # 1. copy source code
    src_fn = PROJ_ROOT / "data" / "subjects" / "poppler-26.06.0.tar.xz"
    dest_fn = work_dir / "poppler-26.06.0.tar.xz"
    if not src_fn.exists():
        print(f"Source file {src_fn} does not exist")
        return False

    shutil.copy(src_fn, dest_fn)

    # 2. extract source code
    shutil.unpack_archive(dest_fn, work_dir)
    src_dir = work_dir / "poppler-26.06.0"

    if not src_dir.exists():
        print(f"Source directory {src_dir} does not exist after extraction")
        return False

    # 3. build and install
    os.chdir(src_dir)

    install_dir = work_dir / "install"

    # Use a clean build dir so a stale CMake cache can't override our flags
    build_dir = src_dir / "build"
    if build_dir.exists():
        shutil.rmtree(build_dir)
    build_dir.mkdir()
    os.chdir(build_dir)

    # For baseline coverage builds we need gcov instrumentation on both the
    # compile step (--coverage emits .gcno) and the link step (pulls in libgcov).
    compiler_flags = "-g -O0"
    if for_baseline_fuzz:
        compiler_flags += " --coverage -fno-inline"

    cmd = [
        "cmake",
        "..",
        "-DBUILD_SHARED_LIBS=OFF",
        "-DCMAKE_C_COMPILER=gclang",
        "-DCMAKE_CXX_COMPILER=gclang++",
        f"-DCMAKE_INSTALL_PREFIX={install_dir}",
        "-DCMAKE_BUILD_TYPE=debug",
        f"-DCMAKE_CXX_FLAGS={compiler_flags}",
        f"-DCMAKE_C_FLAGS={compiler_flags}",
        "-DBUILD_MANUAL_TESTS=OFF",
        "-DENABLE_GPGME=OFF",
        "-DENABLE_LIBCURL=OFF",
        "-DENABLE_BOOST=OFF",
        "-DENABLE_QT5=OFF",
        "-DENABLE_QT6=OFF",
        "-DENABLE_GLIB=OFF",
        "-DENABLE_GOBJECT_INTROSPECTION=OFF",
        "-DENABLE_CPP=OFF",
        "-DENABLE_GTK_DOC=OFF",
        "-DBUILD_GTK_TESTS=OFF",
        "-DBUILD_QT5_TESTS=OFF",
        "-DBUILD_QT6_TESTS=OFF",
        "-DBUILD_CPP_TESTS=OFF",
        "-DENABLE_LIBTIFF=OFF",
        "-DENABLE_LIBOPENJPEG=none",
        "-DENABLE_LCMS=OFF",
        "-DENABLE_NSS3=OFF",
    ]
    if for_baseline_fuzz:
        # libpoppler is static (BUILD_SHARED_LIBS=OFF), so EXE linker flags are
        # what matter; SHARED kept harmless in case shared is re-enabled.
        cmd.append("-DCMAKE_EXE_LINKER_FLAGS=--coverage")
        cmd.append("-DCMAKE_SHARED_LINKER_FLAGS=--coverage")
    subprocess.run(cmd)

    cmd = ["make", "-j", "24"]
    subprocess.run(cmd)

    cmd = ["make", "install"]
    subprocess.run(cmd)

    return True


def build_xpdf(work_dir: Path, for_baseline_fuzz: bool=False) -> bool:
    # 1. copy source code
    src_fn = PROJ_ROOT / "data" / "subjects" / "xpdf-4.06.tar.gz"
    dest_fn = work_dir / "xpdf-4.06.tar.gz"
    if not src_fn.exists():
        print(f"Source file {src_fn} does not exist")
        return False

    shutil.copy(src_fn, dest_fn)

    # 2. extract source code
    shutil.unpack_archive(dest_fn, work_dir)
    src_dir = work_dir / "xpdf-4.06"

    if not src_dir.exists():
        print(f"Source directory {src_dir} does not exist after extraction")
        return False

    # 3. build and install
    os.chdir(src_dir)

    install_dir = work_dir / "install"

    # Use a clean build dir so a stale CMake cache can't override our flags
    build_dir = src_dir / "build"
    if build_dir.exists():
        shutil.rmtree(build_dir)
    build_dir.mkdir()
    os.chdir(build_dir)

    # For baseline coverage builds we need gcov instrumentation on both the
    # compile step (--coverage emits .gcno) and the link step (pulls in libgcov).
    compiler_flags = "-g -O0"
    if for_baseline_fuzz:
        compiler_flags += " --coverage -fno-inline"

    cmd = [
        "cmake",
        "..",
        "-DCMAKE_C_COMPILER=gclang",
        "-DCMAKE_CXX_COMPILER=gclang++",
        f"-DCMAKE_INSTALL_PREFIX={install_dir}",
        "-DCMAKE_BUILD_TYPE=Debug",
        f"-DCMAKE_C_FLAGS={compiler_flags}",
        f"-DCMAKE_CXX_FLAGS={compiler_flags}",
        "-DBUILD_SHARED_LIBS=OFF",
        "-DCMAKE_DISABLE_FIND_PACKAGE_Qt5Widgets=1",
        "-DCMAKE_DISABLE_FIND_PACKAGE_Qt6Widgets=1",
    ]
    if for_baseline_fuzz:
        # Tools link static libs (BUILD_SHARED_LIBS=OFF), so EXE linker flags are
        # what matter; SHARED kept harmless in case shared is re-enabled.
        cmd.append("-DCMAKE_EXE_LINKER_FLAGS=--coverage")
        cmd.append("-DCMAKE_SHARED_LINKER_FLAGS=--coverage")
    subprocess.run(cmd)

    cmd = ["make", "-j", "24"]
    subprocess.run(cmd)

    cmd = ["make", "install"]
    subprocess.run(cmd)

    return True


def build_pspp(work_dir: Path, for_baseline_fuzz: bool=False) -> bool:
    # 1. copy source code
    src_fn = PROJ_ROOT / "data" / "subjects" / "pspp-2.1.1.tar.gz"
    dest_fn = work_dir / "pspp-2.1.1.tar.gz"
    if not src_fn.exists():
        print(f"Source file {src_fn} does not exist")
        return False

    shutil.copy(src_fn, dest_fn)

    # 2. extract source code
    shutil.unpack_archive(dest_fn, work_dir)
    src_dir = work_dir / "pspp-2.1.1"

    if not src_dir.exists():
        print(f"Source directory {src_dir} does not exist after extraction")
        return False

    # 3. build and install
    os.chdir(src_dir)

    install_dir = work_dir / "install"

    # For baseline coverage builds we need gcov instrumentation on both the
    # compile step (--coverage emits .gcno) and the link step. libtool links
    # via the linker driver, so pass LDFLAGS=--coverage too.
    compiler_flags = "-g -O0"
    if for_baseline_fuzz:
        compiler_flags += " --coverage -fno-inline"

    cmd = [
        "./configure",
        "--disable-shared",
        "CC=gclang",
        "CXX=gclang++",
        "--without-gui",
        "--without-perl-module",
        f"--prefix={install_dir}",
        f"CFLAGS={compiler_flags}",
        f"CXXFLAGS={compiler_flags}",
    ]
    if for_baseline_fuzz:
        cmd.append("LDFLAGS=--coverage")
    subprocess.run(cmd)

    cmd = ["make", "-j", "24"]
    subprocess.run(cmd)

    cmd = ["make", "install"]
    subprocess.run(cmd)

    return True


def build_libtiff(work_dir: Path, for_baseline_fuzz: bool=False) -> bool:
    # 1. copy source code
    src_fn = PROJ_ROOT / "data" / "subjects" / "libtiff-4.7.1.tar.gz"
    dest_fn = work_dir / "libtiff-4.7.1.tar.gz"
    if not src_fn.exists():
        print(f"Source file {src_fn} does not exist")
        return False

    shutil.copy(src_fn, dest_fn)

    # 2. extract source code
    shutil.unpack_archive(dest_fn, work_dir)
    src_dir = work_dir / "libtiff-4.7.1"

    if not src_dir.exists():
        print(f"Source directory {src_dir} does not exist after extraction")
        return False

    # 3. build and install
    os.chdir(src_dir)

    install_dir = work_dir / "install"

    # autogen.sh here is a plain autoreconf wrapper (regenerates configure) and
    # does not forward configure args, so the two steps stay separate.
    cmd = ["./autogen.sh"]
    subprocess.run(cmd)

    # For baseline coverage builds we need gcov instrumentation on both the
    # compile step (--coverage emits .gcno) and the link step. libtool links
    # via the linker driver, so pass LDFLAGS=--coverage too.
    compiler_flags = "-g -O0"
    if for_baseline_fuzz:
        compiler_flags += " --coverage -fno-inline"

    cmd = [
        "./configure",
        "--disable-shared",
        "CC=gclang",
        "CXX=gclang++",
        f"--prefix={install_dir}",
        f"CFLAGS={compiler_flags}",
        f"CXXFLAGS={compiler_flags}",
    ]
    if for_baseline_fuzz:
        cmd.append("LDFLAGS=--coverage")
    subprocess.run(cmd)

    cmd = ["make", "-j", "24"]
    subprocess.run(cmd)

    cmd = ["make", "install"]
    subprocess.run(cmd)

    return True


def build_libxml2(work_dir: Path, for_baseline_fuzz: bool=False) -> bool:
    # 1. copy source code
    src_fn = PROJ_ROOT / "data" / "subjects" / "libxml2-2.15.3.tar.gz"
    dest_fn = work_dir / "libxml2-2.15.3.tar.gz"
    if not src_fn.exists():
        print(f"Source file {src_fn} does not exist")
        return False

    shutil.copy(src_fn, dest_fn)

    # 2. extract source code
    shutil.unpack_archive(dest_fn, work_dir)
    src_dir = work_dir / "libxml2-2.15.3"

    if not src_dir.exists():
        print(f"Source directory {src_dir} does not exist after extraction")
        return False

    # 3. build and install
    os.chdir(src_dir)

    install_dir = work_dir / "install"

    # For baseline coverage builds we need gcov instrumentation on both the
    # compile step (--coverage emits .gcno) and the link step. libtool links
    # via the linker driver, so pass LDFLAGS=--coverage too.
    compiler_flags = "-g -O0"
    if for_baseline_fuzz:
        compiler_flags += " --coverage -fno-inline"

    # libxml2's autogen.sh regenerates configure AND forwards these args to it
    # ($srcdir/configure $EXTRA_ARGS "$@"), so do it in one step rather than
    # running a separate argless ./autogen.sh (which would configure twice).
    cmd = [
        "./autogen.sh",
        "--disable-shared",
        "CC=gclang",
        "CXX=gclang++",
        f"--prefix={install_dir}",
        f"CFLAGS={compiler_flags}",
        f"CXXFLAGS={compiler_flags}",
    ]
    if for_baseline_fuzz:
        cmd.append("LDFLAGS=--coverage")
    subprocess.run(cmd)

    cmd = ["make", "-j", "24"]
    subprocess.run(cmd)

    cmd = ["make", "install"]
    subprocess.run(cmd)

    return True


def build_expat(work_dir: Path, for_baseline_fuzz: bool=False) -> bool:
    # 1. copy source code
    src_fn = PROJ_ROOT / "data" / "subjects" / "expat-2.8.1.tar.gz"
    dest_fn = work_dir / "expat-2.8.1.tar.gz"
    if not src_fn.exists():
        print(f"Source file {src_fn} does not exist")
        return False

    shutil.copy(src_fn, dest_fn)

    # 2. extract source code
    shutil.unpack_archive(dest_fn, work_dir)
    src_dir = work_dir / "expat-2.8.1"

    if not src_dir.exists():
        print(f"Source directory {src_dir} does not exist after extraction")
        return False

    # 3. build and install
    os.chdir(src_dir)

    install_dir = work_dir / "install"

    # For baseline coverage builds we need gcov instrumentation on both the
    # compile step (--coverage emits .gcno) and the link step. libtool links
    # via the linker driver, so pass LDFLAGS=--coverage too.
    compiler_flags = "-g -O0"
    if for_baseline_fuzz:
        compiler_flags += " --coverage -fno-inline"

    cmd = [
        "./configure",
        "--disable-shared",
        "CC=gclang",
        "CXX=gclang++",
        f"--prefix={install_dir}",
        f"CFLAGS={compiler_flags}",
        f"CXXFLAGS={compiler_flags}",
    ]
    if for_baseline_fuzz:
        cmd.append("LDFLAGS=--coverage")
    subprocess.run(cmd)

    cmd = ["make", "-j", "24"]
    subprocess.run(cmd)

    cmd = ["make", "install"]
    subprocess.run(cmd)

    return True


BUILD_LOGICS_MAP = {
    "libav": build_libav,
    "bison": build_bison,
    "libjpeg-turbo": build_libjpeg_turbo,
    "libdwarf": build_libdwarf,
    "exiv2": build_exiv2,
    "ffmpeg": build_ffmpeg,
    "GraphicsMagick": build_GraphicsMagick,
    "ghostpdl": build_ghostpdl,
    "jasper": build_jasper,
    "mpg123": build_mpg123,
    "nasm": build_nasm,
    "binutils": build_binutils,
    "poppler": build_poppler,
    "xpdf": build_xpdf,
    "pspp": build_pspp,
    "libtiff": build_libtiff,
    "libxml2": build_libxml2,
    "expat": build_expat,
}

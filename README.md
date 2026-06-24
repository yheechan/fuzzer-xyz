# focalpp_baseline_runner

## TODO:
1. Implement angora build logic
2. Implement aflpp build logic
3. Implement aflpp fuzz pipeline

## Prerequisites
1. Clang/LLVM 20 (default environment setting)
    ```
    $ wget https://github.com/llvm/llvm-project/releases/download/llvmorg-20.1.8/llvm-project-20.1.8.src.tar.xz
    $ cmake -GNinja -S llvm-project-20.1.8.src/llvm -B llvm_build -DCMAKE_INSTALL_PREFIX=`pwd`/llvm_20.1.8_install -DCMAKE_BUILD_TYPE=Release -DLLVM_TARGETS_TO_BUILD=X86 -DBUILD_SHARED_LIBS=OFF -DLLVM_ENABLE_PROJECTS="clang;compiler-rt;clang-tools-extra;lld"
    $ cmake --build llvm_build --target install
    ```

2. Clang/LLVM 12
    ```
    $ gaster23.swtv:/ssd_home/yangheechan/downloads/llvm-project-12.0.1.src.editted.tar.gz
    $ cmake -GNinja -S llvm-project-12.0.1.src/llvm -B llvm-12.0.1-build -DCMAKE_INSTALL_PREFIX=`pwd`/llvm_12.0.1_install -DCMAKE_BUILD_TYPE=Release -DLLVM_TARGETS_TO_BUILD=X86 -DBUILD_SHARED_LIBS=OFF -DLLVM_ENABLE_PROJECTS="clang;compiler-rt;clang-tools-extra;lld" CC=gcc-9 CXX=g++-9 -DCOMPILER_RT_HAS_FLOAT16=OFF
    $ cmake --build llvm-12.0.1-build --target install
    ```

3. [Rustup](https://rustup.rs/) (>= 1.31)
    ```
    curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y
    ```
4. Python 3.10.12+
    ```
    $ python3 -m venv .venv
    $ source .venv/bin/activate
    $ pip install -r requirements.txt
    ```

## Submodules build
```
$ git submodules update --init --recursive
$ cd AFLplusplus; make -j20
$ cd bb_cov; make -j20

# Set LLVM version to 12.0.1
$ cd Angora; ./buid/build.sh
```

## Configurations to set before excution
* ``src/utils/configs.py``
    * fuzzing configs:
        * ``NUM_FUZZER``: # of processes to run fuzzing
    * experiment configs:
        * ``LLVM20_ROOT``, ``LLVM12_ROOT``: absolute paths to llvm's install directory
        * ``ANGORA_RUN_DIR``: must have less character than ``SUN_LEN``

## Usage:
1. Compile target
    ```
    $ python3 focalpp_baseline_runner/src/scripts/compile.py [-h] -o OUTPUT_DIR -t TARGET_PROGRAM -f FUZZER
    ```

2. Run fuzz
    * Command to run fuzzing for 24 hours
    ```
    $ timeout --signal=2 24h python3 focalpp_baseline_runner/src/scripts/fuzz.py [-h] -o OUTPUT_DIR -t TARGET_PROGRAM -f FUZZER [-fid FUZZ_ID] -e EXPERIMENT_NAME
    ```

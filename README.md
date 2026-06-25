# fuzzer-xyz

## TODO:
- [x] Implement angora driver compilation
- [x] Implement angora fuzz pipeline
- [x] Implement script to run fuzzing tasks on server
- [ ] Execute 24 hours angora fuzz for 13 target programs
- [ ] Implement gcov/bbcov coverage measuring script
- [ ] Implement aflpp fuzz pipeline
- [ ] Crash analysis

## My Notes:
- command to execute angora_fuzzer
```
$ export ANGORA_FUZZER=/ssd_home/yangheechan/research/focalpp/baseline_fuzzer_reproduction/fuzzer-xyz/Angora/bin/fuzzer

$ timeout --signal=2 30s $ANGORA_FUZZER -i fuzzer-xyz/data/init_seeds/<target_seed_dir> -o /ssd_home/yangheechan/.angora_runs/<fuzz_id> -j 4 -t <taint> -- <fast> <argv>
```
- set repoisitory on server
```
$ parallel-ssh -h ~/.hosts/set_focalpp -i "cd /ssd_home/yangheechan/research/focalpp/baseline_fuzzer_reproduction/; git clone https://github.com/yheechan/fuzzer-xyz.git;"
$ parallel-ssh -h ~/.hosts/set_focalpp -i "cd /ssd_home/yangheechan/research/focalpp/baseline_fuzzer_reproduction/fuzzer-xyz; git submodule update --init --recursive;"

$ parallel-ssh -h ~/.hosts/focalpp_servers -i "cd /ssd_home/yangheechan/research/focalpp/baseline_fuzzer_reproduction/fuzzer-xyz/bb_cov; make -j20;"
$ parallel-ssh -h ~/.hosts/focalpp_servers -i "cd /ssd_home/yangheechan/research/focalpp/baseline_fuzzer_reproduction/fuzzer-xyz/Angora; export PATH=/ssd_home/yangheechan/downloads/llvm_12.0.1_install/bin:$PATH; export LD_LIBRARY_PATH=/ssd_home/yangheechan/downloads/llvm_12.0.1_install/lib:$LD_LIBRARY_PATH; llvm-config --version"
$ parallel-ssh -h ~/.hosts/focalpp_servers -i "cd /ssd_home/yangheechan/research/focalpp/baseline_fuzzer_reproduction/fuzzer-xyz/Angora; export PATH=/ssd_home/yangheechan/downloads/llvm_12.0.1_install/bin:$PATH; export LD_LIBRARY_PATH=/ssd_home/yangheechan/downloads/llvm_12.0.1_install/lib:$LD_LIBRARY_PATH; ./build/build.sh"
```

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
$ git submodule update --init --recursive
$ cd AFLplusplus; make -j20
$ cd bb_cov; make -j20

# Add llvm-12/bin/ to PATH
# Add llvm-12/lib/ to LD_LIBRARY_PATH
$ cd Angora; ./buid/build.sh
```

## Configurations to set before excution
* ``src/utils/configs.py``
    * experiment configs:
        * ``LLVM20_ROOT``, ``LLVM12_ROOT``: absolute paths to llvm's install directory
        * ``ANGORA_RUN_DIR``: must have less character than ``SUN_LEN``

## Usage:
1. Compile target
    ```
    $ time python3 fuzzer-xyz/src/scripts/compile.py [-h] -o OUTPUT_DIR -t TARGET_PROGRAM -f FUZZER
    ```

2. Run fuzz
    * Command to run fuzzing for 24 hours on local
        ```
        $ timeout --signal=2 24h python3 fuzzer-xyz/src/scripts/fuzz.py [-h] -o OUTPUT_DIR -t TARGET_PROGRAM -f FUZZER -e EXPERIMENT_NAME [-p NUM_FUZZERS] [-fid FUZZ_ID]
        ```
    * Command to run fuzzing for 24 hours on server (currently implementing)
        ```
        $ time python3 fuzzer-xyz/src/scripts/fuzz_on_server.py [-h] -o OUTPUT_DIR -t TARGET_PROGRAM -f FUZZER -s SERVER_ADDRESS -e EXPERIMENT_NAME [-p NUM_FUZZERS] [-d DURATION]
        ```

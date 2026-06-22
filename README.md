# focalpp_baseline_runner


## Prerequisites
1. Clang/LLVM 12
    ```
    $ wget https://github.com/llvm/llvm-project/releases/download/llvmorg-12.0.1/llvm-project-12.0.1.src.tar.xz
    $ cmake -GNinja -S llvm-project-12.0.1.src/llvm -B llvm-12.0.1-build -DCMAKE_CXX_FLAGS="-include cstdint" -DCMAKE_INSTALL_PREFIX=`pwd`/llvm_12.0.1_install -DCMAKE_BUILD_TYPE=Release -DLLVM_TARGETS_TO_BUILD=X86 -DBUILD_SHARED_LIBS=OFF -DLLVM_ENABLE_PROJECTS="clang;compiler-rt;clang-tools-extra;lld" -DCOMPILER_RT_HAS_FLOAT16=OFF CC=gcc-9 CXX=g++-9
    $ cmake -GNinja -S llvm-project-12.0.1.src/llvm -B llvm-12.0.1-build -DCMAKE_INSTALL_PREFIX=`pwd`/llvm_12.0.1_install -DCMAKE_BUILD_TYPE=Release -DLLVM_TARGETS_TO_BUILD=X86 -DBUILD_SHARED_LIBS=OFF -DLLVM_ENABLE_PROJECTS="clang;compiler-rt;clang-tools-extra;lld" CC=gcc-9 CXX=g++-9 -DCOMPILER_RT_HAS_FLOAT16=OFF
    $ cmake --build llvm-12.0.1-build --target install
    ```
    "보통 버전 이렇게 소스로 설치하고 세팅을 PATH export해주나요 아니면 alternatives로 순서 바꾸나요?"
    ```
    export PATH=/path-to-clang/bin:$PATH
    export LD_LIBRARY_PATH=/path-to-clang/lib:$LD_LIBRARY_PATH
    ```

2. [Rustup](https://rustup.rs/)
    ```
    curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y
    ```
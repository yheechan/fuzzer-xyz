from pathlib import Path

# Angora's prebuilt LLVM passes use the legacy PassManagerBuilder API, which was
# removed after LLVM ~12. The system clang is 20.x, so angora-clang must be
# pointed at an LLVM 12.0.1 backend via ANGORA_CC/ANGORA_CXX (see build_logics).
LLVM20_ROOT = Path("/home/yangheechan/Downloads/llvm_20.0.1_install")
LLVM12_ROOT = Path("/home/yangheechan/Downloads/llvm_12.0.1_install")

# Angora binds a Unix-domain forkserver socket at <-o>/tmp/forksrv_socket_<id>;
# sockaddr_un caps that path at 108 bytes (SUN_LEN). The experiment output tree
# is far too deep, so Angora runs in this SHORT directory and we symlink the
# experiment's fuzz_outputs to it. Keep this base path short.
ANGORA_RUN_DIR = Path("/ssd_home/yangheechan/.angora_runs")
SUN_LEN = 108

NUM_FUZZERS = 4

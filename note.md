# Notes

## command to execute angora_fuzzer
```
$ export ANGORA_FUZZER=/ssd_home/yangheechan/research/focalpp/baseline_fuzzer_reproduction/fuzzer-xyz/Angora/bin/fuzzer

$ timeout --signal=2 30s $ANGORA_FUZZER -i fuzzer-xyz/data/init_seeds/<target_seed_dir> -o /ssd_home/yangheechan/.angora_runs/<fuzz_id> -j 4 -t <taint> -- <fast> <argv>
```



## set repoisitory on server
```
mkdir -p /ssd_home/yangheechan/research/focalpp/baseline_fuzzer_reproduction/;
git clone https://github.com/yheechan/fuzzer-xyz.git;
cd fuzzer-xyz/; python3 -m venv .venv; source .venv/bin/activate;
git submodule update --init --recursive;

cd bb_cov; make -j20;
cd ../Angora; export PATH=/ssd_home/yangheechan/downloads/llvm_12.0.1_install/bin:$PATH; export LD_LIBRARY_PATH=/ssd_home/yangheechan/downloads/llvm_12.0.1_install/lib:$LD_LIBRARY_PATH; ./build/build.sh
cd ../AFLplusplus/; make AFL_CLANG_FLTO=-flto=full -j20;
```

deactivate; cd baseline_fuzzer_reproduction; source fuzzer-xyz/.venv/bin/activate; clear;
time python3 fuzzer-xyz/src/scripts/fuzz_on_server.py -o outputs/xmlwf -t xmlwf -f angora -s gaster22.swtv -e angora_4_proc_exp -p 4 -d 24h


## Target selection
- removed:
    - 특별 이휴:
        - bison: angora 실행 도중 4~12시간 정도 지나고 끊김 (원인 모름).
        - gs: angora 실행 정상 종료 안됨
    - 큰 프로젝트:
        - ffmpeg
    - C++:
        - exiv2
        - pdftohtml
        - pdftopng
    - not clear reason to be removed:
        - avconv
        - pspp
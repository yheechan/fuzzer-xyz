/*
 * Non-invasive Angora taint-source model for open64().
 *
 * Programs built with -D_FILE_OFFSET_BITS=64 (libav/ffmpeg, etc.) call open64
 * instead of open. Angora's bundled io_func.c only models open, so the input
 * fd is never registered as a taint source and the track run yields zero
 * constraints. We supply __dfsw_open64 here and route open64 to it via an
 * extra abilist (ANGORA_TAINT_RULE_LIST) + this object (ANGORA_TAINT_CUSTOM_RULE),
 * leaving the Angora submodule untouched.
 */
#include <fcntl.h>
#include <stdarg.h>
#include <stdint.h>
#include <string.h>
#include <unistd.h>

typedef uint32_t dfsan_label;            /* matches Angora's defs.h */
extern void __angora_io_add_fd(int fd);  /* defined in libruntime.a */

#ifndef O_TMPFILE
#define O_TMPFILE 020200000
#endif
#define NEEDS_MODE(f) (((f) & O_CREAT) || ((f) & O_TMPFILE))

/* Mirrors __dfsw_open in Angora/llvm_mode/external_lib/io_func.c. The magic
 * substring "cur_input" is the fuzzer's per-run input file (FUZZING_INPUT_FILE). */
__attribute__((visibility("default")))
int __dfsw_open64(const char *path, int oflags, dfsan_label path_label,
                  dfsan_label flag_label, dfsan_label *va_labels,
                  dfsan_label *ret_label, ...) {
  int mode = 0;
  if (NEEDS_MODE(oflags)) {
    va_list arg;
    va_start(arg, ret_label);
    mode = va_arg(arg, int);
    va_end(arg);
  }
  int fd = open(path, oflags, mode);
  if (fd >= 0 && strstr(path, "cur_input")) {
    __angora_io_add_fd(fd);
  }
  *ret_label = 0;
  return fd;
}

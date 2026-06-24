/*
 * Non-invasive Angora taint-source models for functions Angora's bundled
 * io_func.c does not model. Routed in via an extra abilist
 * (ANGORA_TAINT_RULE_LIST) + this object (ANGORA_TAINT_CUSTOM_RULE), leaving
 * the Angora submodule untouched.
 *
 *  - open64(): programs built with -D_FILE_OFFSET_BITS=64 (libav/ffmpeg, ...)
 *    call open64 instead of open, so the input fd is never registered as a
 *    taint source and the track run yields zero constraints.
 *  - dup()/dup2()/dup3(): libxml2 (xmllint) dup()s the input fd then reads via
 *    the copy; dup is unmodeled, so the duplicated fd loses its taint-source
 *    registration -> zero constraints. Propagate the registration here.
 */
#define _GNU_SOURCE
#include <fcntl.h>
#include <stdarg.h>
#include <stdint.h>
#include <string.h>
#include <unistd.h>

typedef uint32_t dfsan_label;               /* matches Angora's defs.h */
extern void __angora_io_add_fd(int fd);     /* add_fuzzing_fd    (libruntime.a) */
extern int  __angora_io_find_fd(int fd);    /* is_fuzzing_fd     (libruntime.a) */
extern void __angora_io_remove_fd(int fd);  /* remove_fuzzing_fd (libruntime.a) */

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

/* If the source fd is the tainted input fd, the duplicate must be too. */
__attribute__((visibility("default")))
int __dfsw_dup(int oldfd, dfsan_label oldfd_label, dfsan_label *ret_label) {
  int newfd = dup(oldfd);
  if (newfd >= 0 && __angora_io_find_fd(oldfd)) {
    __angora_io_add_fd(newfd);
  }
  *ret_label = 0;
  return newfd;
}

__attribute__((visibility("default")))
int __dfsw_dup2(int oldfd, int newfd, dfsan_label oldfd_label,
                dfsan_label newfd_label, dfsan_label *ret_label) {
  int r = dup2(oldfd, newfd);
  if (r >= 0) {
    if (__angora_io_find_fd(oldfd))
      __angora_io_add_fd(r);
    else if (__angora_io_find_fd(r))
      __angora_io_remove_fd(r);  /* r was the input fd, now repurposed */
  }
  *ret_label = 0;
  return r;
}

__attribute__((visibility("default")))
int __dfsw_dup3(int oldfd, int newfd, int flags, dfsan_label oldfd_label,
                dfsan_label newfd_label, dfsan_label flags_label,
                dfsan_label *ret_label) {
  int r = dup3(oldfd, newfd, flags);
  if (r >= 0) {
    if (__angora_io_find_fd(oldfd))
      __angora_io_add_fd(r);
    else if (__angora_io_find_fd(r))
      __angora_io_remove_fd(r);
  }
  *ret_label = 0;
  return r;
}

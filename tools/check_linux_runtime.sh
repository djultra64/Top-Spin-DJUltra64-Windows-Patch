#!/bin/sh
# djultra64: run before loading the private Python or graphics runtime.
required=2.42
actual=$(getconf GNU_LIBC_VERSION 2>/dev/null) || actual=
case "$actual" in
    'glibc '*) actual=${actual#glibc } ;;
    *) printf '%s\n' 'This Linux runtime requires glibc 2.42 or newer on x86-64 Linux.' >&2; exit 1 ;;
esac
major=${actual%%.*}
minor=${actual#*.}
minor=${minor%%.*}
case "$major:$minor" in
    *[!0-9:]*|:*|*:) printf '%s\n' 'Could not identify the system glibc version.' >&2; exit 1 ;;
esac
if [ "$major" -lt 2 ] || { [ "$major" -eq 2 ] && [ "$minor" -lt 42 ]; }; then
    printf 'This Linux runtime requires glibc %s or newer; this system has %s.\n' "$required" "$actual" >&2
    printf '%s\n' 'Use the supported Linux build or a runtime rebuilt for your distribution.' >&2
    exit 1
fi
if [ "$(uname -m)" != x86_64 ]; then
    printf '%s\n' 'This Linux runtime requires x86-64 Linux.' >&2
    exit 1
fi

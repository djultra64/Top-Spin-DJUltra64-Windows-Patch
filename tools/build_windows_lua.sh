#!/usr/bin/env bash
# Windows Lua patch-tool integration: djultra64. Lua keeps its authentic MIT notice.
set -euo pipefail
if [[ $# -ne 3 ]]; then
    echo 'Usage: build_windows_lua.sh LUA_ARCHIVE ZIG_EXECUTABLE FRESH_DESTINATION' >&2
    exit 2
fi
repo_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
lua_archive="$(realpath -- "$1")"
zig_executable="$(realpath -- "$2")"
destination="$(realpath -m -- "$3")"
if [[ -e "$destination" ]]; then
    echo 'Destination exists; choose a fresh build directory.' >&2
    exit 2
fi
verify_hash() {
    local expected="$1" path="$2" actual
    actual="$(sha256sum -- "$path")"
    actual="${actual%% *}"
    if [[ "$actual" != "$expected" ]]; then
        echo "SHA256 mismatch: $path" >&2
        exit 1
    fi
}
verify_hash 1193a61b0e08acaa6eee0eecf29709179ee49c71baebc59b682a25c3b5a45671 "$lua_archive"
verify_hash 2858dc89dbbfdd08cceda1b841e7fd0a793a1a67b49f150bc3d0d1de44ed7f51 "$zig_executable"
if [[ "$("$zig_executable" version)" != '0.15.2' ]]; then
    echo 'Pinned Zig 0.15.2 Linux x86-64 compiler required.' >&2
    exit 1
fi
mkdir -p -- "$destination/sources"
tar -xzf "$lua_archive" -C "$destination/sources"
lua_src="$destination/sources/lua-5.0.3"
(
    cd -- "$lua_src"
    git apply --unsafe-paths "$repo_dir/patches/lua50-topspin-format.patch"
    git apply --unsafe-paths "$repo_dir/patches/lua50-windows-tool.patch"
)
verify_hash e2fbcfb778b8d7a5efebf3df6b7bc8a6c92baa41d26273a945c97c36088f0b60 "$lua_src/src/llimits.h"
export ZIG_GLOBAL_CACHE_DIR="$destination/compiler-cache"
export ZIG_LOCAL_CACHE_DIR="$destination/compiler-local-cache"
"$zig_executable" cc \
    -target x86_64-windows-gnu -O2 -static \
    -DUSE_DLL=0 -DUSE_POPEN=0 -DUSE_TMPNAME=0 \
    -I"$lua_src/include" -I"$lua_src/src" \
    "$lua_src"/src/*.c "$lua_src"/src/lib/*.c "$lua_src/src/lua/lua.c" \
    -o "$destination/lua.exe"
mkdir -p -- "$destination/licenses"
cp -- "$lua_src/COPYRIGHT" "$destination/licenses/Lua-5.0.3-COPYRIGHT"
zig_root="$(dirname -- "$zig_executable")"
cp -- "$zig_root/LICENSE" "$destination/licenses/Zig-LICENSE"
cp -- "$zig_root/lib/libc/mingw/COPYING" "$destination/licenses/mingw-w64-COPYING"
# LLD build identifiers depend on source/cache paths. Verify all other bytes.
python3 - "$destination/lua.exe" <<'PYVERIFY'
import hashlib
from pathlib import Path
import sys
raw = bytearray(Path(sys.argv[1]).read_bytes())
if len(raw) != 316928 or raw[:2] != b'MZ' or raw[0x49e38:0x49e3c] != b'RSDS':
    raise SystemExit('Unexpected pinned Windows Lua PE layout')
# Fixed locations belong to this exact compiler/source/flag combination.
# Exclude only COFF/debug timestamps and the CodeView build identifier.
for offset, size in [(0x80, 4), (0x49e04, 4), (0x49e20, 4), (0x49e3c, 16)]:
    raw[offset:offset + size] = bytes(size)
expected = 'f5dbf8f80d6ce06244450526c401cd2dba749d35fcf210891d87e6df8bc9d0de'
if hashlib.sha256(raw).hexdigest() != expected:
    raise SystemExit('Windows Lua content differs beyond linker build identifiers')
print('Windows Lua content matches the release tool; linker identifiers excluded.')
PYVERIFY
sha256sum -- "$destination/lua.exe"

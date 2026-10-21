# Lua 5.0.3 bytecode compatibility

Own compatibility changes: **djultra64**. Lua retains its authentic authors and
MIT notice in `licenses/lua-5.0.3/COPYRIGHT`.

`patches/lua50-topspin-format.patch` contains the shared bytecode differences
from upstream Lua 5.0.3. `patches/lua50-windows-tool.patch` adds the Windows
allocation-accounting adjustment described below. It contains no original game script, compiled chunk,
table, archive, executable or asset. The private root-level `luac.out` must
never be published.

The format uses 32-bit serialized string sizes and instructions on the tested
64-bit Linux host, stores local-variable debug records before line records,
omits serialized upvalue-name records, and uses the game's numeric format
sentinel. The reader and writer agree on this layout. Keep this dedicated
interpreter separate from a system Lua installation. It is intended for trusted,
locally supplied inputs with the hash guards in `tools/menu_quit.py`, not
arbitrary downloaded bytecode. Sizes above the 32-bit range are unsupported.

## Build on Linux

Required tools: a C compiler, GNU Make, Git, tar, and a SHA-256 utility. Obtain
[upstream Lua 5.0.3](https://www.lua.org/ftp/lua-5.0.3.tar.gz) locally at
`build/lua-5.0.3.tar.gz`. The verified archive SHA-256 is:

```text
1193a61b0e08acaa6eee0eecf29709179ee49c71baebc59b682a25c3b5a45671
```

From the source repository root, with a fresh `build/lua-5.0.3` destination:

```sh
mkdir -p build
sha256sum build/lua-5.0.3.tar.gz
tar -xzf build/lua-5.0.3.tar.gz -C build
git apply --directory=build/lua-5.0.3 patches/lua50-topspin-format.patch
make -C build/lua-5.0.3 clean
make -C build/lua-5.0.3
python3 -m unittest discover -s tests -p test_menu_quit.py -v
```

Compare the printed archive hash before extraction. Clean before rebuilding an
existing tree: the upstream Makefiles do not track header dependencies. The interpreter and compiler
are `build/lua-5.0.3/bin/lua` and `build/lua-5.0.3/bin/luac`. This recipe was
verified by rebuilding from the untouched archive and running the synthetic menu
tests. It requires no original game files and performs no global installation.
The public repository distributes the source patch and license notice; compiled
Lua programs and upstream source archives remain local build products.


## Rebuild the Windows x64 patch tool on Linux

Own Windows build integration: **djultra64**. The dedicated tool uses the same
serialized bytecode format as the Linux build. The additional source patch
changes internal `lu_mem` accounting from `unsigned long` to `size_t` and adjusts
its maximum. On Windows x64 (LLP64), `unsigned long` is only 32 bits while
pointers and `size_t` are 64 bits. This change affects internal allocations;
serialized sizes remain 32 bits and Lua numbers remain doubles.

Obtain the official
[Zig 0.15.2 Linux x86-64 archive](https://ziglang.org/download/0.15.2/zig-x86_64-linux-0.15.2.tar.xz).
Its SHA-256 is:

```text
02aa270f183da276e5b5920b1dac44a63f1a49e55050ebde3aecc9eb82f93239
```

Verify that hash before extraction. Keep the complete compiler directory,
including its `lib` tree. The rebuild helper accepts a local Lua archive, the
extracted Zig executable, and a destination that does not yet exist:

```sh
bash tools/build_windows_lua.sh \
  build/lua-5.0.3.tar.gz \
  build/Windows-Patch-Tools/compiler/zig-x86_64-linux-0.15.2/zig \
  build/Windows-Lua-Rebuild
```

The helper downloads nothing and installs no host packages. It verifies the Lua
archive and Zig executable hashes, extracts a fresh Lua tree, applies both source
patches, and uses Zig 0.15.2 with `-target x86_64-windows-gnu -O2 -static`.
Dynamic C-library loading, subprocess pipes and `tmpnam` are disabled with
`USE_DLL=0`, `USE_POPEN=0` and `USE_TMPNAME=0`. The resulting `lua.exe` is a
Windows x64 console tool for the installer, independent of the 32-bit game.
The previously staged release tool has this SHA-256:

```text
192a8d7f812fa9ab90ff16309c2b2eef5c8df4aead68316e4cf17f9c2b243bc9
```

The helper copies authentic Lua, Zig and mingw-w64 notices into the build's
`licenses` directory. Preserve them when redistributing the executable. The
upstream sources and compiler remain local build inputs; the public repository
contains only the compatibility patches, build recipe and required notices.
The helper also needs Python 3 for its final content verification. Fresh build
paths change LLD's reproducible-build timestamps and CodeView identifier. A
fresh build differed in only 20 metadata bytes from the staged release tool;
every code/data byte and all imports matched. The helper leaves the binary
untouched and checks the complete PE after excluding only those identifier
fields (28 bytes reserved), using normalized SHA-256:

```text
f5dbf8f80d6ce06244450526c401cd2dba749d35fcf210891d87e6df8bc9d0de
```

The verifier uses the pinned PE layout and rejects an unexpected size or
layout. It prints the actual whole-file SHA-256 for the new build. This verifies
content reproducibility while documenting linker metadata differences; it does
not run the game or establish native Windows gameplay compatibility.

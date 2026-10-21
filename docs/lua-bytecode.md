# Lua 5.0.3 bytecode compatibility

Own compatibility changes: **djultra64**. Lua retains its authentic authors and
MIT notice in `licenses/lua-5.0.3/COPYRIGHT`.

`patches/lua50-topspin-format.patch` contains the complete local differences
from upstream Lua 5.0.3. It contains no original game script, compiled chunk,
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

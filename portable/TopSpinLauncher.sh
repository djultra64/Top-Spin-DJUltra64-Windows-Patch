#!/usr/bin/env bash
# djultra64 — prefer the packaged Python runtime, then development Python.
set -euo pipefail
root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
python_bin="$root/runtime/python/bin/python3"
if [[ -x "$python_bin" ]]; then
    if [[ -f "$root/runtime/linux/check-abi.sh" ]]; then
        sh "$root/runtime/linux/check-abi.sh"
    fi
    export PYTHONHOME="$root/runtime/python"
    export LD_LIBRARY_PATH="$root/runtime/python/lib64${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
    export TK_LIBRARY="$root/runtime/python/share/tk9.0"
    export TCL_LIBRARY="$root/runtime/python/share/tcl9.0"
else
    python_bin=python3
fi
cd -- "$root"
exec "$python_bin" -m launcher --game-dir "$root" "$@"

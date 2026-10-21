#!/usr/bin/env bash
# djultra64 — all starts use the saved portable graphics/input settings.
set -euo pipefail
root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
exec "$root/TopSpinLauncher.sh" --play "$@"

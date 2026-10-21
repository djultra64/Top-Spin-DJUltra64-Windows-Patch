"""Remove local build prefixes from a staged Gamescope ELF. djultra64.

Only two known NUL-terminated path constants are rewritten, preserving all ELF
sizes and offsets. The public wrapper supplies GAMESCOPE_SCRIPT_PATH explicitly.
"""
import argparse
import hashlib
from pathlib import Path
import re
import subprocess


PATHS = (
    (rb'/[^\x00\n]*?/build/third-party/gamescope/devel/usr/lib64', b'/usr/lib64'),
    (rb'/[^\x00\n]*?/build/Gamescope-SDK-Staging/share/gamescope/scripts',
     b'/usr/share/gamescope/scripts'),
)


def sanitized_bytes(raw):
    if not raw.startswith(b'\x7fELF'):
        raise ValueError('Choose a Gamescope ELF binary.')
    result = raw
    for pattern, replacement in PATHS:
        matches = list(re.finditer(pattern + rb'(?=\x00)', result))
        if len(matches) > 1:
            raise ValueError('Ambiguous Gamescope build path.')
        for match in reversed(matches):
            old = match.group()
            if len(replacement) > len(old):
                raise ValueError('Replacement would change ELF offsets.')
            result = result[:match.start()] + replacement.ljust(len(old), b'\x00') + result[match.end():]
    return result


def sanitize(path):
    path = Path(path)
    dynamic = subprocess.run(['readelf', '--dynamic', str(path)], check=True,
                             capture_output=True, text=True).stdout
    if re.search(r'\((?:RUNPATH|RPATH)\)', dynamic):
        raise ValueError('Remove build RPATH with the build system before sanitizing.')
    before = path.read_bytes()
    after = sanitized_bytes(before)
    if after != before:
        path.write_bytes(after)
    return {'before_sha256': hashlib.sha256(before).hexdigest(),
            'after_sha256': hashlib.sha256(after).hexdigest(),
            'same_size': len(before) == len(after)}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('binary', type=Path)
    print(sanitize(parser.parse_args().binary))

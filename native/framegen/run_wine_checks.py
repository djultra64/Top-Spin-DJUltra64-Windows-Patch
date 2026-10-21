#!/usr/bin/env python3
"""Synthetic Windows DLL checks under Wine; never starts or reads a game.

Author: djultra64. SPDX-License-Identifier: MIT
Wine manual-chain results do not establish native Windows loader compatibility.
"""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
from check_interpolation import controls, measure


def ppm(path):
    magic, size, maximum, pixels = path.read_bytes().split(b'\n', 3)
    width, height = map(int, size.split())
    if magic != b'P6' or maximum != b'255' or len(pixels) != width * height * 3:
        raise ValueError('Unexpected synthetic PPM')
    return width, height, pixels


def check_static(directory):
    for frame in (8, 9):
        width, height, pixels = ppm(directory / ('afmf_generated_' + str(frame) + '.ppm'))
        expected = bytearray(width * height * 3)
        for y in range(200, 264):
            for x in range(64, 128):
                value = 160 if ((x - 64) * 7 + y * 13) % 5 < 2 else 255
                expected[(y * width + x) * 3:(y * width + x) * 3 + 3] = bytes([value] * 3)
        if pixels != expected:
            raise AssertionError('Static output differs from the identical source image')
        lines = (directory / ('afmf_flow_' + str(frame) + '.txt')).read_text().splitlines()[1:]
        if any(int(component) != 0 for line in lines for component in line.split()):
            raise AssertionError('Static input produced nonzero optical flow')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--wine', type=Path, required=True)
    parser.add_argument('--build', type=Path, required=True)
    parser.add_argument('--prefix', type=Path, required=True)
    parser.add_argument('--fixtures', choices=('motion', 'static', 'both'), default='both')
    args = parser.parse_args()
    build = args.build.resolve()
    environment = {key: value for key, value in os.environ.items() if not key.startswith('AFMF_')}
    for key in ('WAYLAND_DISPLAY', 'VK_LAYER_PATH', 'VK_ADD_LAYER_PATH', 'VK_INSTANCE_LAYERS'):
        environment.pop(key, None)
    environment.update(WINEPREFIX=str(args.prefix.resolve()), WINEDEBUG='-all',
                       WINEDLLOVERRIDES='winemenubuilder.exe=d', VK_LOADER_LAYERS_DISABLE='~implicit~',
                       AFMF_LOG='3', AFMF_TEST_FRAME_MS='20', AFMF_ACQUIRE_TIMEOUT_US='16000',
                       AFMF_GOVERNOR='0', AFMF_MIN_FPS='0')
    output = build / 'wine-checks'
    output.mkdir(exist_ok=True)
    results = {}
    for bits in (32, 64):
        runtime = build / ('win' + str(bits))
        for static in {'motion': (False,), 'static': (True,), 'both': (False, True)}[args.fixtures]:
            label = str(bits) + ('-static' if static else '-motion')
            dump = output / label
            dump.mkdir(exist_ok=True)
            current = dict(environment, AFMF_TEST_LAYER_DLL='Z:' + str(runtime / ('afmf' + str(bits) + '.dll')),
                           AFMF_DUMP_DIR='Z:' + str(dump), AFMF_TEST_STATIC='1' if static else '0')
            with (output / (label + '.log')).open('w') as log:
                subprocess.run(['xvfb-run', '-a', str(args.wine.resolve()),
                                str(runtime / 'afmf-synthetic-test.exe')],
                               env=current, stdout=log, stderr=subprocess.STDOUT, check=True, timeout=55)
            text = (output / (label + '.log')).read_text()
            if 'after 120 presents: 119 generated' not in text or 'presented 120 frames through' not in text:
                raise AssertionError('Synthetic presentation/generation count mismatch')
            if static:
                check_static(dump)
                results[label] = {'same_source_pixels': True, 'zero_optical_flow': True, 'generated': 119}
            else:
                checked = {}
                for frame in (8, 9):
                    width, height, pixels = ppm(dump / ('afmf_generated_' + str(frame) + '.ppm'))
                    checked[str(frame)] = measure(pixels, width, frame)
                    checked['negative_controls_' + str(frame)] = controls(width, height, frame)
                    if not checked[str(frame)]['pass']:
                        raise AssertionError('Generated image failed motion-compensated edge check')
                results[label] = checked
            print('PASS', label, flush=True)
    results['limitation'] = 'Native Windows DLL manually chained above Wine Vulkan on llvmpipe/Xvfb; native Windows not tested'
    (output / 'results.json').write_text(json.dumps(results, indent=2) + '\n')


if __name__ == '__main__':
    main()

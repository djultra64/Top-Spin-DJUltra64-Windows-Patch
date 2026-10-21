#!/usr/bin/env python3
"""Check synthetic GPU dumps for translated edges, rejecting repeats and blends.

Author: djultra64. SPDX-License-Identifier: MIT
The upstream harness separately verifies optical flow; centroid alone is weak.
"""
import argparse
import json
from pathlib import Path


def region(pixels, width, x0, x1):
    values = [pixels[(y * width + x) * 3 + channel]
              for y in range(208, 256) for x in range(x0, x1) for channel in range(3)]
    return sum(values) / len(values)


def measure(pixels, width, frame):
    midpoint = 64 + frame * 8 - 4
    # These strips lie inside the true midpoint square, outside the overlap of
    # both source squares. A 50/50 blend is at most 188 here even when encoded
    # from linear light into sRGB. The actual translated edge should be solid.
    left = region(pixels, width, midpoint + 1, midpoint + 4)
    right = region(pixels, width, midpoint + 61, midpoint + 64)
    old_only = region(pixels, width, midpoint - 4, midpoint)
    new_only = region(pixels, width, midpoint + 64, midpoint + 68)
    return {'left_edge_mean': left, 'right_edge_mean': right,
            'old_only_mean': old_only, 'new_only_mean': new_only,
            'pass': left > 195 and right > 195 and old_only < 64 and new_only < 64}


def synthetic(width, height, left, value=255):
    pixels = bytearray(width * height * 3)
    for y in range(200, 264):
        for x in range(left, left + 64):
            pixels[(y * width + x) * 3:(y * width + x) * 3 + 3] = bytes([value] * 3)
    return pixels


def controls(width, height, frame):
    previous = synthetic(width, height, 64 + (frame - 1) * 8)
    current = synthetic(width, height, 64 + frame * 8)
    ideal = synthetic(width, height, 64 + frame * 8 - 4)
    assert measure(ideal, width, frame)['pass'], 'Ideal midpoint must pass'
    samples = {'repeated_previous': previous, 'repeated_current': current,
               'alpha_blend_encoded': bytes((a + b) // 2 for a, b in zip(previous, current)),
               'alpha_blend_linear_srgb': bytes(a if a == b else 188 for a, b in zip(previous, current))}
    results = {name: measure(pixels, width, frame) for name, pixels in samples.items()}
    if any(result['pass'] for result in results.values()):
        raise AssertionError('Repeat or alpha-blend negative control incorrectly passed')
    return results


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('directory', type=Path)
    args = parser.parse_args()
    output = {}
    for frame in (8, 9):
        path = args.directory / ('afmf_generated_' + str(frame) + '.ppm')
        magic, size, maximum, pixels = path.read_bytes().split(b'\n', 3)
        width, height = map(int, size.split())
        if magic != b'P6' or maximum != b'255' or len(pixels) != width * height * 3:
            raise ValueError('Unexpected synthetic PPM format')
        output[str(frame)] = measure(pixels, width, frame)
        output['controls_' + str(frame)] = controls(width, height, frame)
        if not output[str(frame)]['pass']:
            print(json.dumps(output, indent=2))
            raise SystemExit('GPU output failed translated-edge energy check')
    print(json.dumps(output, indent=2))


if __name__ == '__main__':
    main()

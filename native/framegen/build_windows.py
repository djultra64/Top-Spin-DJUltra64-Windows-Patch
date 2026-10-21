#!/usr/bin/env python3
"""Cross-build the pinned Windows AFMF port; own integration: djultra64.

No host packages, game files, network, or native machine access are needed.
SPDX-License-Identifier: MIT
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import struct
import subprocess
import tarfile

PIN = 'bc56e5bd0e3a6c328aedef664d0d36363fb58b36'
SOURCE_SHA256 = '2fccc4a6238aad1cb58ea69ffb3f775ee9644a18b4c149c987fce6290b273dcd'
ROOT = Path(__file__).resolve().parents[2]


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def run(command, environment=None):
    subprocess.run([str(item) for item in command], check=True, env=environment)


def shaders(source, output, glslang):
    """Same shader permutations and target as pinned upstream CMakeLists.txt."""
    output.mkdir(parents=True, exist_ok=True)
    fidelity = source / 'shaders/fidelityfx'
    permutations = []
    passes = ('prepare_luma', 'compute_luminance_pyramid', 'generate_scd_histogram',
              'compute_scd_divergence', 'compute_optical_flow_advanced_pass_v5',
              'filter_optical_flow_pass_v5', 'scale_optical_flow_advanced_pass_v5')
    for item in passes:
        name = 'ffx_opticalflow_' + item
        if not item.endswith('_v5'):
            name += '_pass'
        permutations.append((name, fidelity / 'passes' / (name + '.glsl'),
                             ['FFX_GPU=1', 'FFX_GLSL=1', 'FFX_OPTICALFLOW_OPTION_HDR_COLOR_INPUT=0']))
    name = 'ffx_opticalflow_compute_optical_flow_advanced_pass_v5'
    permutations.append((name + '_int16', fidelity / 'passes' / (name + '.glsl'),
                         ['FFX_GPU=1', 'FFX_GLSL=1', 'FFX_OPTICALFLOW_OPTION_HDR_COLOR_INPUT=0', 'AFMF_SAD_INT16=1']))
    for suffix, defines in (
        ('rgba8', ['AFMF_OUT_FORMAT=rgba8', 'AFMF_SWAP_RB=0']),
        ('rgba8_bgra', ['AFMF_OUT_FORMAT=rgba8', 'AFMF_SWAP_RB=1']),
        ('rgb10a2', ['AFMF_OUT_FORMAT=rgb10_a2', 'AFMF_SWAP_RB=0']),
        ('rgba16f', ['AFMF_OUT_FORMAT=rgba16f', 'AFMF_SWAP_RB=0']),
        ('noformat', ['AFMF_OUT_FORMAT_NONE=1', 'AFMF_SWAP_RB=0']),
    ):
        permutations.append(('afmf_interpolate_' + suffix, source / 'shaders/afmf_interpolate.comp', defines))
    for suffix, define in (('rgba8', 'AFMF_OUT_FORMAT=rgba8'), ('rgb10a2', 'AFMF_OUT_FORMAT=rgb10_a2'),
                           ('rgba16f', 'AFMF_OUT_FORMAT=rgba16f'), ('noformat', 'AFMF_OUT_FORMAT_NONE=1')):
        permutations.append(('afmf_ingest_' + suffix, source / 'shaders/afmf_ingest.comp', [define]))
    for suffix in ('rgba8', 'rgba16f'):
        permutations.append(('afmf_downsample_' + suffix, source / 'shaders/afmf_downsample.comp',
                             ['AFMF_OUT_FORMAT=' + suffix]))
    header = ['/* Generated from pinned upstream GLSL, Windows build by djultra64. */',
              '#pragma once', '#include <stddef.h>', '#include <stdint.h>']
    for name, shader, defines in permutations:
        binary = output / (name + '.spv')
        run([glslang, '-V', '--target-env', 'vulkan1.1', '-S', 'comp',
             *('-D' + define for define in defines), '-I' + str(fidelity), '-o', binary, shader])
        data = binary.read_bytes()
        words = struct.unpack('<' + str(len(data) // 4) + 'I', data)
        header += ['static const uint32_t ' + name + '_spv[] = {' +
                   ','.join(hex(word) for word in words) + '};',
                   'static const size_t ' + name + '_spv_size = ' + str(len(data)) + ';']
    result = output / 'afmf_spirv.h'
    result.write_text('\n'.join(header) + '\n')
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--archive', type=Path, default=ROOT / 'build/third-party/afmf-linux/source.tar.gz')
    parser.add_argument('--zig', type=Path, default=ROOT / 'build/Windows-Patch-Tools/compiler/zig-x86_64-linux-0.15.2/zig')
    parser.add_argument('--vulkan-headers', type=Path, default=ROOT / 'build/deps/root/usr/include')
    parser.add_argument('--glslang', type=Path, default=ROOT / 'build/deps/root/usr/bin/glslang')
    parser.add_argument('--output', type=Path, default=ROOT / 'build/afmf-windows-repro')
    args = parser.parse_args()
    args.archive = args.archive.resolve()
    args.output = args.output.resolve()
    if digest(args.archive) != SOURCE_SHA256:
        raise ValueError('Pinned upstream archive hash mismatch')
    args.output.mkdir(parents=True, exist_ok=True)
    source = args.output / 'source'
    if source.exists():
        raise ValueError('Output source already exists; choose a fresh output directory')
    extracted = args.output / 'unpack'
    with tarfile.open(args.archive) as archive:
        archive.extractall(extracted, filter='data')
    shutil.copytree(extracted / ('afmf-linux-' + PIN), source)
    for patch in ('afmf-windows.patch', 'afmf-windows-harness.patch'):
        run(['git', 'apply', '--unsafe-paths', '--directory=' + str(source), ROOT / 'patches' / patch])
    headers = args.output / 'headers'
    for name in ('vulkan', 'vk_video'):
        shutil.copytree(args.vulkan_headers.resolve() / name, headers / name)
    embedded = shaders(source, args.output / 'shaders', args.glslang.resolve())
    own = ROOT / 'native/framegen'
    environment = dict(os.environ, ZIG_GLOBAL_CACHE_DIR=str(args.output / 'compiler-cache'),
                       ZIG_LOCAL_CACHE_DIR=str(args.output / 'local-cache'))
    runtime_sources = sorted((source / 'src').glob('*.c'))
    test_sources = sorted((source / 'tests').glob('headless*.c'))
    built = []
    for bits, target in ((32, 'x86-windows-gnu'), (64, 'x86_64-windows-gnu')):
        destination = args.output / ('win' + str(bits))
        destination.mkdir()
        common = [args.zig.resolve(), 'cc', '-target', target, '-O2', '-g0', '-std=c11',
                  '-Wall', '-Wextra', '-Werror', '-ffile-prefix-map=' + str(ROOT) + '=.',
                  '-I' + str(own), '-I' + str(headers), '-lwinmm']
        dll = destination / ('afmf' + str(bits) + '.dll')
        run([*common, '-shared', '-I' + str(embedded.parent), *runtime_sources,
             own / 'windows_compat.c', own / ('afmf' + str(bits) + '.def'), '-o', dll], environment)
        layer = {'file_format_version': '1.0.0', 'layer': {
            'name': 'VK_LAYER_AFMF', 'type': 'GLOBAL', 'library_path': './' + dll.name,
            'api_version': '1.4.341', 'implementation_version': '5',
            'description': 'AFMF Windows port by djultra64; upstream afmf-linux 1.3.1',
            'functions': {'vkNegotiateLoaderLayerInterfaceVersion': 'vkNegotiateLoaderLayerInterfaceVersion'}}}
        (destination / 'afmf-windows.json').write_text(json.dumps(layer, indent=2) + '\n')
        harness = destination / 'afmf-synthetic-test.exe'
        run([*common, '-DVK_USE_PLATFORM_WIN32_KHR', '-DVK_NO_PROTOTYPES', '-DAFMF_TEST_MANUAL_CHAIN',
             *test_sources, own / 'windows_compat.c', own / 'windows_harness_bridge.c',
             '-luser32', '-o', harness], environment)
        run([*common, '-DAFMF_WINDOWS_COMPAT_TEST', own / 'windows_compat_test.c', own / 'windows_compat.c',
             '-o', destination / 'windows-compat-test.exe'], environment)
        built.extend([dll, harness])
    notices = args.output / 'licenses'
    notices.mkdir()
    for name, path in {
        'afmf-linux-MIT.txt': source / 'LICENSE',
        'djultra64-Windows-integration-MIT.txt': own / 'LICENSE',
        'Zig-MIT.txt': args.zig.resolve().parent / 'LICENSE',
        'mingw-w64-COPYING.txt': args.zig.resolve().parent / 'lib/libc/mingw/COPYING',
        'THIRD_PARTY_NOTICES.txt': own / 'THIRD_PARTY_NOTICES.txt',
    }.items():
        shutil.copyfile(path, notices / name)
    # AMD's own complete notice is at the start of each vendored header.
    amd = (source / 'shaders/fidelityfx/ffx_core.h').read_text().split('/// @defgroup')[0]
    (notices / 'AMD-FidelityFX-MIT.txt').write_text(amd)
    manifest = {'author': 'djultra64', 'upstream_commit': PIN, 'archive_sha256': SOURCE_SHA256,
                'compiler': subprocess.check_output([args.zig.resolve(), 'version'], text=True).strip(),
                'compiler_sha256': digest(args.zig),
                'glslang_sha256': digest(args.glslang), 'shader_header_sha256': digest(embedded),
                'integration_files': [
                    {'path': str(path.relative_to(ROOT)), 'sha256': digest(path)}
                    for path in sorted(own.iterdir()) if path.is_file()
                ] + [
                    {'path': 'patches/' + name, 'sha256': digest(ROOT / 'patches' / name)}
                    for name in ('afmf-windows.patch', 'afmf-windows-harness.patch')
                ],
                'files': [{'path': str(path.relative_to(args.output)), 'sha256': digest(path)}
                          for path in built],
                'status': 'Cross-built; run synthetic and native Windows acceptance tests before activation'}
    (args.output / 'provenance.json').write_text(json.dumps(manifest, indent=2) + '\n')


if __name__ == '__main__':
    main()

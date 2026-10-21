"""Public release boundary tests using synthetic files only. djultra64."""
import hashlib
import json
from pathlib import Path
import tempfile
import os
import subprocess
import tarfile
import unittest
from unittest.mock import patch
import zipfile
from tools.build_patch_release import (
    BINARY_DESTINATIONS, LINUX_SOURCE_ONLY_FILES, FRAMEGEN_DESTINATIONS, FRAMEGEN_NOTICES, FRAMEGEN_DXVK_LICENSE, SOURCE_FILES, SOURCE_ONLY_FILES, build_release, prepare_payload, safe_name)


def sha(data): return hashlib.sha256(data).hexdigest()


class PatchReleaseTests(unittest.TestCase):
    def fixture(self, root):
        def write(name, data):
            path = root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
        for name in SOURCE_FILES + SOURCE_ONLY_FILES: write(name, ('own-source:' + name).encode())
        base = 'assets/input/xelu/'
        for name in ('mapping.json', 'Readme.original.txt'): write(base + name, b'CC0 fixture')
        write(base + 'provenance.json', json.dumps({'license': 'CC0-1.0', 'files': []}).encode())
        entries = []
        for index, destination in enumerate(sorted(BINARY_DESTINATIONS) + ['ApplyPatch.exe', 'licenses/own.txt']):
            source = 'build/reviewed/' + str(index) + '.bin'
            data = ('own-or-permissive:' + destination).encode()
            write(source, data)
            entries.append({'source': source, 'destination': destination, 'sha256': sha(data),
                'role': 'installer' if destination == 'ApplyPatch.exe' else 'overlay',
                'notices': ['licenses/own.txt']})
        for role in ('lua', 'input', 'save_drives', 'options_delete'):
            source = 'build/reviewed/' + role + '.bin'
            data = ('own-or-permissive:' + role).encode()
            write(source, data)
            entries.append({'source': source, 'role': role, 'sha256': sha(data), 'notices': ['licenses/own.txt']})
        return {'files': entries}, {'files': [{'sha256': sha(b'ORIGINAL GAME BYTES')}]}

    def linux_fixture(self, root, *, abi_failure=False):
        reviewed, inventory = self.fixture(root)
        reviewed['platform'] = 'linux'
        reviewed['files'] = [item for item in reviewed['files'] if
            'destination' not in item or item['destination'].startswith(('licenses/', 'runtime/input/'))]
        for name in LINUX_SOURCE_ONLY_FILES + ('docs/linux.md',):
            path = root / name; path.parent.mkdir(parents=True, exist_ok=True); path.write_bytes(b'Own Linux documentation')
        for name in ('portable/TopSpinLauncher.sh', 'portable/Play-TopSpin.sh'):
            (root / name).write_bytes(b'#!/bin/sh\nexit 0\n')
        lua = next(item for item in reviewed['files'] if item.get('role') == 'lua')
        (root / lua['source']).write_bytes(b'\x7fELFsynthetic-linux-lua'); lua['sha256'] = sha(b'\x7fELFsynthetic-linux-lua')
        runtime = {'gamescope': 'runtime/linux/bin/gamescope', 'afmf_layer': 'runtime/linux/afmf',
            'video_libraries': ['runtime/linux/lib64/libvideo.so'],
            'video_plugins': 'runtime/linux/gstreamer-1.0', 'library_path': 'runtime/linux/lib64'}
        data = {
            'runtime/python/bin/python3': b'#!/bin/sh\nprintf "%s\\n" "$PYTHONHOME" "$PYTHONPATH" "$LD_LIBRARY_PATH" "$@" > "$PATCH_TEST_MARKER"\nprintf \'{"metadata":true}\\n\'\nprintf \'synthetic diagnostic\\n\' >&2\nexit "${PATCH_TEST_FAIL:-0}"\n',
            'runtime/linux/check-abi.sh': b'#!/bin/sh\nexit ' + (b'1' if abi_failure else b'0') + b'\n',
            'runtime/linux/bin/gamescope': b'#!/bin/sh\nexit 0\n',
            'runtime/linux/lib64/libvideo.so': b'\x7fELFsynthetic-video-library',
            'runtime/linux/gstreamer-1.0/libgstvideo.so': b'\x7fELFsynthetic-plugin',
            'runtime/linux/afmf/libafmf-linux.so': b'\x7fELFsynthetic-interpolation',
            'runtime/linux/afmf/afmf-linux.json': json.dumps({'layer': {
                'name': 'VK_LAYER_AFMF', 'library_path': './libafmf-linux.so'}}).encode(),
            'runtime/python/lib64/python3.14/urllib/__init__.py': b'',
            'runtime/python/lib64/python3.14/site-packages/PIL/py.typed': b'',
            '.portable/runtime.json': json.dumps(runtime).encode(),
        }
        for index, (destination, payload) in enumerate(data.items()):
            source = 'build/reviewed/linux-' + str(index) + '.bin'
            (root / source).write_bytes(payload)
            if destination == 'runtime/linux/bin/gamescope': (root / source).chmod(0o755)
            executable = destination in ('runtime/python/bin/python3', 'runtime/linux/check-abi.sh')
            reviewed['files'].append({'source': source, 'destination': destination, 'sha256': sha(payload),
                'notices': ['licenses/own.txt'], **({'executable': True} if executable else {})})
        return reviewed, inventory

    def test_linux_tar_contains_only_regular_staged_files_and_safe_executable_modes(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder); reviewed, inventory = self.linux_fixture(root)
            destination = root / 'linux.tar.gz'
            build_release(root, destination, reviewed, inventory)
            with tarfile.open(destination) as archive:
                members = archive.getmembers()
                self.assertTrue(all(member.isfile() and member.uid == member.gid == 0 for member in members))
                self.assertTrue(all(member.name == 'Install-Patch.sh' or member.name.startswith('.topspin-patch/') for member in members))
                names = {member.name for member in members}
                self.assertNotIn('Install-Patch.cmd', names)
                self.assertFalse(any(name.endswith(('.cmd', '.exe')) for name in names))
                manifest = json.load(archive.extractfile('.topspin-patch/manifest.json'))
                self.assertEqual(manifest['platform'], 'linux')
                self.assertTrue(manifest['files']['runtime/linux/bin/gamescope']['executable'])
                self.assertEqual(archive.extractfile('.topspin-patch/files/runtime/python/lib64/python3.14/urllib/__init__.py').read(), b'')
                self.assertEqual(archive.extractfile('.topspin-patch/files/runtime/python/lib64/python3.14/site-packages/PIL/py.typed').read(), b'')
                self.assertIn('files/Linux-Readme.md', [item['path'] for item in manifest['files'].values()])
                for member in members:
                    expected = (member.name == 'Install-Patch.sh' or member.name == '.topspin-patch/' + manifest['lua']['path'] or
                        any(member.name == '.topspin-patch/' + item['path'] and item.get('executable') for item in manifest['files'].values()))
                    self.assertEqual(member.mode, 0o755 if expected else 0o644)

    def test_linux_installer_preflight_runs_before_interpreter_and_uses_only_bundled_paths(self):
        for failed in (False, True):
            with self.subTest(abi_failure=failed), tempfile.TemporaryDirectory() as folder:
                root = Path(folder); reviewed, inventory = self.linux_fixture(root, abi_failure=failed)
                destination = root / 'linux.tar.gz'; build_release(root, destination, reviewed, inventory)
                install = root / 'Installed Game'; install.mkdir()
                marker = root / 'python-was-run.txt'
                with tarfile.open(destination) as archive: archive.extractall(install, filter='data')
                result = subprocess.run([str(install / 'Install-Patch.sh'), '--check'],
                    env={**os.environ, 'PATCH_TEST_MARKER': str(marker)}, capture_output=True, text=True)
                self.assertEqual(result.returncode, 1 if failed else 0, result.stderr)
                self.assertEqual(marker.exists(), not failed)
                if not failed:
                    output = marker.read_text()
                    self.assertIn(str(install / '.topspin-patch/files/runtime/python'), output)
                    self.assertIn(str(install / '.topspin-patch/files/runtime/python/lib64'), output)
                    self.assertIn('tools.install_patch', output)
                    self.assertIn('--check', output)

    def test_linux_wrapper_shows_friendly_results_and_keeps_metadata_in_private_log(self):
        for check_only, fail in ((False, False), (True, False), (False, True)):
            with self.subTest(check_only=check_only, fail=fail), tempfile.TemporaryDirectory() as folder:
                root = Path(folder); reviewed, inventory = self.linux_fixture(root)
                destination = root / 'linux.tar.gz'; build_release(root, destination, reviewed, inventory)
                install = root / 'Existing Game'; install.mkdir()
                with tarfile.open(destination) as archive: archive.extractall(install, filter='data')
                result = subprocess.run([str(install / 'Install-Patch.sh')] + (['--check'] if check_only else []),
                    env={**os.environ, 'PATCH_TEST_MARKER': str(root / 'marker'),
                         'PATCH_TEST_FAIL': '7' if fail else '0'}, capture_output=True, text=True)
                self.assertEqual(result.returncode, 7 if fail else 0)
                self.assertIn('Preparing the Top Spin patch.', result.stdout)
                log = (install / '.topspin-patch/install.log').read_text()
                self.assertIn('{"metadata":true}', log)
                self.assertIn('synthetic diagnostic', log)
                self.assertNotIn('metadata', result.stdout)
                if fail:
                    self.assertIn('{"metadata":true}', result.stderr)
                    self.assertIn('Patch installation failed.', result.stderr)
                    self.assertNotIn('successfully', result.stdout)
                elif check_only:
                    self.assertIn('Patch validated successfully. No game files were changed.', result.stdout)
                    self.assertEqual(result.stderr, '')
                else:
                    self.assertIn('Patch installed successfully. Open TopSpinLauncher.sh', result.stdout)
                    self.assertEqual(result.stderr, '')

    def test_linux_rejects_windows_files_bad_runtime_and_unsafe_modes_before_archive(self):
        for mutation in ('windows', 'missing_python', 'mode_type', 'execute_json', 'bad_runtime'):
            with self.subTest(mutation=mutation), tempfile.TemporaryDirectory() as folder:
                root = Path(folder); reviewed, inventory = self.linux_fixture(root)
                item = next(entry for entry in reviewed['files'] if entry.get('destination') == '.portable/runtime.json')
                if mutation == 'windows': item['destination'] = 'runtime/windows-framegen/afmf32.dll'
                elif mutation == 'missing_python':
                    reviewed['files'] = [entry for entry in reviewed['files'] if entry.get('destination') != 'runtime/python/bin/python3']
                elif mutation == 'mode_type': item['executable'] = 'true'
                elif mutation == 'execute_json': item['executable'] = True
                else:
                    (root / item['source']).write_bytes(b'{}'); item['sha256'] = sha(b'{}')
                destination = root / 'blocked.tar.gz'
                with self.assertRaises(ValueError): build_release(root, destination, reviewed, inventory)
                self.assertFalse(destination.exists())

    def framegen_fixture(self, root, reviewed, mutation=None):
        manifest_name = '.portable/windows-framegen.json'
        names = FRAMEGEN_DESTINATIONS - {manifest_name}
        data = {name: ('distinct-FG-component:' + name).encode() for name in names}
        layer_name = 'runtime/windows-framegen/VkLayer_AFMF.json'
        library = 'other.dll' if mutation == 'layer_path' else './afmf32.dll'
        data[layer_name] = json.dumps({'layer': {'name': 'VK_LAYER_AFMF', 'library_path': library}}).encode()
        if mutation == 'wrapper_alias':
            data['runtime/windows-framegen/dxvk32/d3d9.dll'] = data['runtime/windows-framegen/dxvk32/d3d8.dll']
        hashes = {name: sha(payload) for name, payload in data.items()}
        if mutation == 'component_hash': hashes['runtime/windows-framegen/afmf32.dll'] = '0' * 64
        if mutation == 'extra_component': hashes['runtime/windows-framegen/unreviewed.dll'] = '0' * 64
        data[manifest_name] = json.dumps({'version': 1, 'files': hashes}).encode()
        if mutation == 'partial': del data[layer_name]
        if mutation == 'unknown_destination': data['runtime/windows-framegen/unreviewed.dll'] = b'unreviewed'
        dxvk_text = b'Authentic synthetic DXVK fixture notice'
        license_pin = patch('tools.build_patch_release.FRAMEGEN_DXVK_LICENSE_SHA256', sha(dxvk_text))
        license_pin.start(); self.addCleanup(license_pin.stop)
        if mutation != 'missing_dxvk_notice': data[FRAMEGEN_DXVK_LICENSE] = dxvk_text
        if mutation == 'altered_dxvk_notice': data[FRAMEGEN_DXVK_LICENSE] += b'changed'
        if mutation != 'missing_notice':
            for destination, source in FRAMEGEN_NOTICES.items():
                data[destination] = (root / source).read_bytes()
            if mutation == 'altered_notice': data[next(iter(FRAMEGEN_NOTICES))] += b'changed'
        for index, (destination, payload) in enumerate(sorted(data.items())):
            source = 'build/reviewed/fg-' + str(index) + '.bin'
            (root / source).write_bytes(payload)
            reviewed['files'].append({'source': source, 'destination': destination,
                'sha256': sha(payload), 'notices': (list(FRAMEGEN_NOTICES) if
                    destination == 'runtime/windows-framegen/afmf32.dll' and mutation != 'missing_notice'
                    else [FRAMEGEN_DXVK_LICENSE] if '/dxvk32/' in destination and mutation != 'missing_dxvk_notice'
                    else ['licenses/own.txt'])})

    def test_optional_framegen_complete_component_and_sources_are_packaged(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder); reviewed, inventory = self.fixture(root)
            self.framegen_fixture(root, reviewed)
            output = prepare_payload(root, reviewed, inventory)
            manifest = json.loads(output['manifest.json'])
            self.assertTrue(FRAMEGEN_DESTINATIONS <= manifest['files'].keys())
            self.assertIn('files/launcher/windows_framegen.py', output)
            self.assertTrue(all('files/' + name in output for name in FRAMEGEN_DESTINATIONS))

    def test_optional_framegen_rejects_partial_corrupt_or_unreviewed_component(self):
        for mutation in ('partial', 'component_hash', 'extra_component', 'layer_path',
                         'wrapper_alias', 'unknown_destination', 'missing_notice', 'altered_notice', 'missing_dxvk_notice', 'altered_dxvk_notice'):
            with self.subTest(mutation=mutation), tempfile.TemporaryDirectory() as folder:
                root = Path(folder); reviewed, inventory = self.fixture(root)
                self.framegen_fixture(root, reviewed, mutation)
                destination = root / 'blocked-framegen.zip'
                with self.assertRaises(ValueError): build_release(root, destination, reviewed, inventory)
                self.assertFalse(destination.exists())

    def test_archive_extracts_only_staging_and_new_entrypoint(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder); reviewed, inventory = self.fixture(root)
            # Private files beside our source are never discovered or copied.
            (root / 'Config.pml').write_bytes(b'PRIVATE KEY')
            (root / 'TopSpin.exe').write_bytes(b'ORIGINAL GAME BYTES')
            destination = root / 'public.zip'
            build_release(root, destination, reviewed, inventory)
            with zipfile.ZipFile(destination) as archive:
                names = archive.namelist()
                self.assertIn('Install-Patch.cmd', names)
                self.assertTrue(all(name == 'Install-Patch.cmd' or name.startswith('.topspin-patch/') for name in names))
                self.assertFalse(any(b'PRIVATE KEY' in archive.read(name) or b'ORIGINAL GAME BYTES' in archive.read(name) for name in names))
                manifest = json.loads(archive.read('.topspin-patch/manifest.json'))
                for descriptor in list(manifest['files'].values()) + list(manifest['stubs'].values()) + [manifest['lua']]:
                    self.assertEqual(sha(archive.read('.topspin-patch/' + descriptor['path'])), descriptor['sha256'])

    def test_embedded_python_installer_uses_bundled_sources(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder); reviewed, inventory = self.fixture(root)
            entry = next(item for item in reviewed['files'] if item.get('destination') == 'ApplyPatch.exe')
            entry.update(role='installer_python', destination='runtime-installer/python.exe')
            for name, data in [('python314.zip', b'library'), ('python314.dll', b'runtime'),
                               ('python314._pth', b'python314.zip\n.\n../files\nLib/site-packages\n')]:
                source = 'build/reviewed/' + name
                (root / source).write_bytes(data)
                reviewed['files'].append({'source': source, 'destination': 'runtime-installer/' + name,
                    'role': 'installer', 'sha256': sha(data), 'notices': ['licenses/own.txt']})
            destination = root / 'python-installer.zip'
            build_release(root, destination, reviewed, inventory)
            with zipfile.ZipFile(destination) as archive:
                command = archive.read('Install-Patch.cmd').decode('ascii')
                self.assertIn('runtime-installer\\python.exe" -I -m tools.install_patch', command)
                self.assertIn('.topspin-patch/files/tools/install_patch.py', archive.namelist())
                self.assertNotIn('.topspin-patch/ApplyPatch.exe', archive.namelist())

    def test_paths_fail_closed(self):
        for name in ('../x', '/x', 'a\\b', 'a/../x', 'x:stream', 'a//b', 'TopSpin.exe',
                     'media/font.rui', 'Config.PML', 'artwork/grid.png', 'T/save', 'file.wad', 'NUL.txt', 'foo/COM1'):
            with self.subTest(name=name), self.assertRaises(ValueError): safe_name(name)

    def test_original_bytes_renamed_as_runtime_are_rejected_without_output(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder); reviewed, inventory = self.fixture(root)
            item = reviewed['files'][0]
            (root / item['source']).write_bytes(b'ORIGINAL GAME BYTES')
            item['sha256'] = sha(b'ORIGINAL GAME BYTES')
            with self.assertRaisesRegex(ValueError, 'Original game content'):
                build_release(root, root / 'blocked.zip', reviewed, inventory)
            self.assertFalse((root / 'blocked.zip').exists())

    def test_hash_notice_manifest_and_destination_fail_closed(self):
        for mutation in ('hash', 'notice', 'destination', 'missing', 'collision'):
            with self.subTest(mutation=mutation), tempfile.TemporaryDirectory() as folder:
                root = Path(folder); reviewed, inventory = self.fixture(root)
                if mutation == 'hash': reviewed['files'][0]['sha256'] = '0' * 64
                elif mutation == 'notice': reviewed['files'][0]['notices'] = []
                elif mutation == 'destination': reviewed['files'][0]['destination'] = 'innocent.txt'
                elif mutation == 'missing': reviewed['files'].pop()
                else:
                    item = dict(reviewed['files'][0]); item['destination'] = item['destination'].upper()
                    reviewed['files'].append(item)
                with self.assertRaises(ValueError): prepare_payload(root, reviewed, inventory)

    def test_file_and_directory_symlinks_are_rejected(self):
        for directory in (False, True):
            with tempfile.TemporaryDirectory() as folder:
                root = Path(folder); reviewed, inventory = self.fixture(root)
                path = root / SOURCE_FILES[0]
                if directory:
                    original = path.parent; moved = root / 'moved'
                    original.rename(moved); original.symlink_to(moved, target_is_directory=True)
                else:
                    path.unlink(); path.symlink_to(root / SOURCE_FILES[1])
                with self.assertRaisesRegex(ValueError, 'Symbolic source'): prepare_payload(root, reviewed, inventory)

    def test_existing_archive_is_not_overwritten(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder); reviewed, inventory = self.fixture(root)
            destination = root / 'public.zip'; destination.write_bytes(b'existing')
            with self.assertRaises(ValueError): build_release(root, destination, reviewed, inventory)
            self.assertEqual(destination.read_bytes(), b'existing')


if __name__ == '__main__': unittest.main()

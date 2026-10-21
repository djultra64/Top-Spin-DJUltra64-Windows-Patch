"""Public release boundary tests using synthetic files only. djultra64."""
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import zipfile
from tools.build_patch_release import (
    BINARY_DESTINATIONS, SOURCE_FILES, SOURCE_ONLY_FILES, build_release, prepare_payload, safe_name)


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

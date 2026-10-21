"""Private portable packaging and read-only integrity contracts."""
import json
import tempfile
import unittest
from pathlib import Path
from launcher.integrity import build_manifest, verify_integrity, write_manifest
from tools.package_portable import package_portable
from tools.verify_build import verify


class IntegrityTests(unittest.TestCase):
    def test_authorized_generated_font_update_preserves_unrelated_checksums(self):
        from launcher.integrity import manifest_with_updates
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);(root/'Media').mkdir()
            (root/'Media/font.rui').write_bytes(b'keyboard');(root/'TopSpin.exe').write_bytes(b'game')
            original=build_manifest(root,['Media/font.rui','TopSpin.exe']);write_manifest(root,original)
            changed=manifest_with_updates(root,{root/'Media/font.rui':b'controller'})
            self.assertEqual(changed['files'][1],original['files'][1])
            self.assertNotEqual(changed['files'][0]['sha256'],original['files'][0]['sha256'])
            self.assertEqual(changed['files'][0]['size'],10)
            with self.assertRaises(ValueError):manifest_with_updates(root,{root/'unlisted':b'data'})

    def test_corruption_missing_and_mutable_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            for name in ['TopSpin.exe','Media/font.rui','Config.pml','T/GlobalOptions/save']:
                path=root/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(b'original')
            write_manifest(root,build_manifest(root,['TopSpin.exe','Media/font.rui','Config.pml','T/GlobalOptions/save']))
            (root/'Config.pml').write_bytes(b'changed')
            (root/'T/GlobalOptions/save').unlink()
            self.assertTrue(verify_integrity(root).ok)
            (root/'TopSpin.exe').write_bytes(b'corrupt')
            (root/'Media/font.rui').unlink()
            result=verify_integrity(root)
            self.assertFalse(result.ok)
            self.assertEqual(result.checked,2)
            self.assertEqual(result.modified,('TopSpin.exe',))
            self.assertEqual(result.missing,('Media/font.rui',))

    def test_untrusted_manifest_paths_and_symlinks_never_read_external_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);(root/'.portable').mkdir()
            for name in ['../secret','/etc/passwd','Media\\..\\secret','C:/Windows/file','T/save']:
                data={'version':1,'files':[{'path':name,'size':0,'sha256':'0'*64}]}
                (root/'.portable/integrity.json').write_text(json.dumps(data))
                with self.subTest(name=name),self.assertRaises(ValueError):verify_integrity(root)
            (root/'escape').symlink_to('/etc/passwd')
            with self.assertRaises(ValueError):build_manifest(root,['escape'])

    def test_relocation_and_build_verifier_use_installed_manifest(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)/'old';root.mkdir();(root/'TopSpin.exe').write_bytes(b'patched')
            write_manifest(root,build_manifest(root,['TopSpin.exe']))
            moved=Path(tmp)/'new folder';root.rename(moved)
            self.assertEqual(verify(moved,None),1)
            self.assertTrue(verify_integrity(moved).ok)
            (moved/'TopSpin.exe').write_bytes(b'bad')
            with self.assertRaisesRegex(ValueError,'TopSpin.exe'):verify(moved,None)

    def test_duplicates_and_invalid_hashes_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);(root/'.portable').mkdir();(root/'x').touch()
            item={'path':'x','size':0,'sha256':'0'*64}
            for files in [[item,item],[dict(item,sha256='broken')]]:
                (root/'.portable/integrity.json').write_text(json.dumps({'version':1,'files':files}))
                with self.assertRaises(ValueError):verify_integrity(root)


class PackageTests(unittest.TestCase):
    def test_sourceless_python_runtime_modules_are_not_discarded_as_caches(self):
        import py_compile
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)/'source';runtime=root/'runtime/python/lib64/python3.14/encodings'
            runtime.mkdir(parents=True);(root/'TopSpin.exe').touch()
            module=runtime/'cp1252.py';module.write_text('value = 1252\n')
            compiled=module.with_suffix('.pyc')
            py_compile.compile(str(module),cfile=str(compiled),doraise=True)
            module.unlink()
            (runtime/'unnecessary.py').write_text('value = 0\n')
            (runtime/'unnecessary.pyc').write_bytes(b'cache beside available source')
            cache=runtime/'__pycache__';cache.mkdir();(cache/'cp1252.pyc').write_bytes(b'cache')
            dest=Path(tmp)/'package'
            package_portable(root,dest,{'files':[{'path':'TopSpin.exe'}]},platform='linux')
            output=dest/compiled.relative_to(root)
            self.assertEqual(output.read_bytes(),compiled.read_bytes())
            self.assertFalse((dest/(runtime/'unnecessary.pyc').relative_to(root)).exists())
            self.assertFalse((dest/cache.relative_to(root)).exists())
            self.assertTrue(verify_integrity(dest).ok)

    def test_private_prompt_baselines_survive_portable_repackaging(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)/'source';baseline=root/'.portable/glyphs/baseline/Media/font.rui'
            baseline.parent.mkdir(parents=True);baseline.write_bytes(b'private user font')
            (root/'.portable/glyphs/style.json').write_text('{"family":"switch"}')
            (root/'TopSpin.exe').touch();dest=Path(tmp)/'package'
            package_portable(root,dest,{'files':[{'path':'TopSpin.exe'}]},platform='linux')
            self.assertEqual((dest/'.portable/glyphs/baseline/Media/font.rui').read_bytes(),b'private user font')
            self.assertTrue((dest/'.portable/glyphs/style.json').is_file())

    def test_internal_runtime_aliases_become_portable_regular_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)/'source';runtime=root/'runtime/python/bin';runtime.mkdir(parents=True)
            (root/'TopSpin.exe').touch();(runtime/'python3.14').write_bytes(b'private interpreter')
            (runtime/'python3').symlink_to('python3.14')
            dest=Path(tmp)/'package'
            package_portable(root,dest,{'files':[{'path':'TopSpin.exe'}]},platform='linux')
            executable=dest/'runtime/python/bin/python3'
            self.assertFalse(executable.is_symlink())
            self.assertEqual(executable.read_bytes(),b'private interpreter')
            self.assertTrue(verify_integrity(dest).ok)

    def test_frozen_runtime_licenses_are_retained(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)/'source';notice=root/'licenses/windows-launcher/CPython-LICENSE.txt'
            notice.parent.mkdir(parents=True);notice.write_text('authentic third-party notice')
            (root/'TopSpin.exe').touch();dest=Path(tmp)/'package'
            package_portable(root,dest,{'files':[{'path':'TopSpin.exe'}]},platform='windows')
            self.assertEqual((dest/'licenses/windows-launcher/CPython-LICENSE.txt').read_text(),notice.read_text())

    def test_private_package_uses_inventory_and_runtime_without_personal_state(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)/'source';root.mkdir();dest=Path(tmp)/'package'
            paths=['TopSpin.exe','Media/base.rui','Config.pml','launcher/gui.py','runtime/input/SDL3.dll',
                   'runtime/input/LICENSE.txt','runtime/python/python.exe','TopSpinLauncher.exe',
                   'T/profile','U/save','.portable/launcher.json','.portable/input.json',
                   'runtime/linux/proton-prefix/secret','runtime/python/__pycache__/x.pyc',
                   'TopSpin.before-options-save.exe','LogGame.txt','portable-build.json','unknown.key']
            for name in paths:
                path=root/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(b'data')
            inventory={'files':[{'path':name} for name in ['TopSpin.exe','Media/base.rui','Config.pml']]}
            report=package_portable(root,dest,inventory)
            self.assertEqual(report['kind'],'private-local-game-package')
            self.assertEqual((dest/'Config.pml').read_bytes(),b'data')
            self.assertTrue((dest/'TopSpinLauncher.exe').is_file())
            self.assertTrue((dest/'runtime/input/LICENSE.txt').is_file())
            for save_root in ['T','U']:
                self.assertTrue((dest/save_root).is_dir(),'Fresh portable save volume must exist')
                self.assertEqual(list((dest/save_root).iterdir()),[])
            for name in paths[8:]:
                if name=='.portable/input.json':continue
                self.assertFalse((dest/name).exists(),name)
            self.assertTrue(verify_integrity(dest).ok)
            self.assertEqual(verify_integrity(dest).checked,report['immutable_files'])
            with self.assertRaisesRegex(ValueError,'exists'):package_portable(root,dest,inventory)

    def test_runtime_contracts_are_copied_and_verified_but_user_settings_are_not(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)/'source';root.mkdir();dest=Path(tmp)/'package'
            (root/'TopSpin.exe').write_bytes(b'game')
            (root/'.portable').mkdir()
            for name in ['input.json','runtime.json']:
                (root/'.portable'/name).write_text('{}')
            package_portable(root,dest,{'files':[{'path':'TopSpin.exe'}]})
            self.assertTrue((dest/'.portable/runtime.json').is_file())
            (dest/'.portable/input.json').write_text('{"corrupt":true}')
            self.assertEqual(verify_integrity(dest).modified,('.portable/input.json',))

    def test_windows_and_linux_packages_keep_only_their_platform_runtime(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)/'source';root.mkdir()
            names=['TopSpin.exe','runtime/linux/lib64/video.so','runtime/python/bin/python3',
                   'runtime/input/SDL3.dll','runtime-windows-launcher/python314.dll',
                   'TopSpinLauncher.exe','TopSpinLauncher.sh','TopSpinLauncher.cmd',
                   'Play-TopSpin.sh','Play-TopSpin.cmd','Play-TopSpin.exe','.portable/runtime.json','d3d8.dll',
                   'artwork/steam/hero.png']
            for name in names:
                path=root/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(b'data')
            inventory={'files':[{'path':'TopSpin.exe'}]}
            for platform,keep,drop in [
                ('windows',['runtime-windows-launcher/python314.dll','TopSpinLauncher.exe',
                            'runtime/input/SDL3.dll','d3d8.dll','TopSpinLauncher.cmd','Play-TopSpin.exe',
                            'artwork/steam/hero.png'],
                           ['runtime/linux/lib64/video.so','runtime/python/bin/python3',
                            '.portable/runtime.json','TopSpinLauncher.sh','Play-TopSpin.sh']),
                ('linux',['runtime/linux/lib64/video.so','runtime/python/bin/python3',
                          'runtime/input/SDL3.dll','.portable/runtime.json','TopSpinLauncher.sh','artwork/steam/hero.png'],
                         ['runtime-windows-launcher/python314.dll','TopSpinLauncher.exe',
                          'TopSpinLauncher.cmd','Play-TopSpin.cmd','Play-TopSpin.exe','d3d8.dll'])]:
                dest=Path(tmp)/platform
                package_portable(root,dest,inventory,platform=platform)
                for name in keep:self.assertTrue((dest/name).is_file(),name)
                for name in drop:self.assertFalse((dest/name).exists(),name)
                self.assertTrue(verify_integrity(dest).ok)

    def test_windows_graphics_marker_is_immutable_but_wrapper_config_is_mutable(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)/'source';root.mkdir();(root/'TopSpin.exe').touch()
            (root/'.portable').mkdir();(root/'.portable/windows-graphics.json').write_text('{}')
            (root/'dgVoodoo.conf').write_text('settings')
            dest=Path(tmp)/'windows'
            package_portable(root,dest,{'files':[{'path':'TopSpin.exe'}]},platform='windows')
            self.assertTrue((dest/'.portable/windows-graphics.json').is_file())
            (dest/'dgVoodoo.conf').write_text('changed')
            self.assertTrue(verify_integrity(dest).ok)
            (dest/'.portable/windows-graphics.json').write_text('changed')
            self.assertFalse(verify_integrity(dest).ok)

    def test_incomplete_or_symlinked_sources_leave_no_partial_package(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)/'source';root.mkdir();dest=Path(tmp)/'package'
            (root/'TopSpin.exe').write_bytes(b'game')
            inventory={'files':[{'path':'TopSpin.exe'},{'path':'Media/missing'}]}
            with self.assertRaises(FileNotFoundError):package_portable(root,dest,inventory)
            self.assertFalse(dest.exists())
            (root/'Config.pml').symlink_to('/etc/passwd')
            with self.assertRaises(ValueError):package_portable(root,dest,{'files':[{'path':'Config.pml'}]})
            self.assertFalse(dest.exists())

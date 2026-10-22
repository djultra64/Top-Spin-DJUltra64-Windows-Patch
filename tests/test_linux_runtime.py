import tempfile
import unittest
from pathlib import Path
from tools.linux_runtime import parse_dependencies, copy_runtime_file, portable_layer_manifest

class LinuxRuntimeTests(unittest.TestCase):
    def test_compositor_wrapper_checks_xwayland_before_starting_binary(self):
        import subprocess
        from tools.linux_runtime import gamescope_wrapper
        with tempfile.TemporaryDirectory(prefix='Graphics runtime ') as tmp:
            root=Path(tmp);(root/'bin').mkdir()
            wrapper=root/'bin/gamescope';wrapper.write_text(gamescope_wrapper());wrapper.chmod(0o755)
            guard=root/'check-abi.sh';guard.write_text('#!/bin/sh\nexit 0\n');guard.chmod(0o755)
            binary=root/'bin/gamescope.bin';binary.write_text('#!/bin/sh\nprintf COMPOSITOR_STARTED\n');binary.chmod(0o755)
            reaper=root/'bin/gamescopereaper';reaper.write_text('#!/bin/sh\nexit 0\n');reaper.chmod(0o755)
            zenity=root/'bin/zenity';zenity.write_text('#!/bin/sh\nexit 0\n');zenity.chmod(0o755)
            for mode in ['missing','not-executable','directory','valid']:
                path=root/'bin/Xwayland'
                if path.exists():
                    if path.is_dir():path.rmdir()
                    else:path.unlink()
                if mode=='directory':path.mkdir()
                elif mode!='missing':
                    path.write_text('#!/bin/sh\nexit 0\n');path.chmod(0o755 if mode=='valid' else 0o644)
                result=subprocess.run([str(wrapper),'--','/usr/bin/true'],capture_output=True,text=True,timeout=2)
                if mode=='valid':
                    self.assertEqual(result.returncode,0);self.assertIn('COMPOSITOR_STARTED',result.stdout)
                else:
                    self.assertNotEqual(result.returncode,0);self.assertNotIn('COMPOSITOR_STARTED',result.stdout)
                    self.assertIn('Xwayland',result.stderr)

    def test_compositor_selects_packaged_reaper_and_rejects_missing_helper(self):
        import os,subprocess
        from tools.linux_runtime import gamescope_wrapper
        with tempfile.TemporaryDirectory(prefix='Graphics helper ') as d:
            root=Path(d);(root/'bin').mkdir();host=root/'host';host.mkdir()
            for path,body in [(root/'bin/Xwayland','exit 0'),(root/'bin/zenity','exit 0'),(root/'check-abi.sh','exit 0'),
                              (root/'bin/gamescopereaper','printf PACKAGED_REAPER'),
                              (host/'gamescopereaper','printf WRONG_HOST_REAPER'),
                              (root/'bin/gamescope.bin','gamescopereaper')]:
                path.write_text('#!/bin/sh\n'+body+'\n');path.chmod(0o755)
            wrapper=root/'bin/gamescope';wrapper.write_text(gamescope_wrapper());wrapper.chmod(0o755)
            env=dict(os.environ,PATH=str(host)+':/usr/bin:/bin')
            result=subprocess.run([str(wrapper)],env=env,capture_output=True,text=True)
            self.assertEqual(result.returncode,0,result.stderr);self.assertEqual(result.stdout,'PACKAGED_REAPER')
            (root/'bin/gamescopereaper').unlink()
            result=subprocess.run([str(wrapper)],env=env,capture_output=True,text=True)
            self.assertNotEqual(result.returncode,0);self.assertIn('gamescopereaper',result.stderr)
            self.assertNotIn('WRONG_HOST_REAPER',result.stdout)

    def test_zenity_shim_restores_host_loader_environment_for_real_child(self):
        import os,subprocess
        from tools.linux_runtime import host_zenity_wrapper
        with tempfile.TemporaryDirectory(prefix='Host helper ') as d:
            root=Path(d);host=root/'own-host-zenity';host.write_text('#!/bin/sh\nprintf "%s|%s|%s|%s|%s" "${LD_LIBRARY_PATH+x}" "${LD_LIBRARY_PATH-}" "${LD_PRELOAD+x}" "${LD_PRELOAD-}" "$1"\n');host.chmod(0o755)
            shim=root/'zenity';shim.write_text(host_zenity_wrapper(host));shim.chmod(0o755)
            env=dict(os.environ,LD_LIBRARY_PATH=str(root/'private libs'),
                     TOPSPIN_HOST_LD_LIBRARY_PATH_SET='1',TOPSPIN_HOST_LD_LIBRARY_PATH='/host/original libs',
                     TOPSPIN_HOST_LD_PRELOAD_SET='0')
            env.pop('LD_PRELOAD',None)
            result=subprocess.run([str(shim),'argument with spaces'],env=env,capture_output=True,text=True)
            self.assertEqual(result.returncode,0,result.stderr)
            self.assertEqual(result.stdout,'x|/host/original libs|||argument with spaces')
            env['TOPSPIN_HOST_LD_LIBRARY_PATH_SET']='0';env['TOPSPIN_HOST_LD_PRELOAD_SET']='1';env['TOPSPIN_HOST_LD_PRELOAD']=''
            result=subprocess.run([str(shim),'next'],env=env,capture_output=True,text=True)
            self.assertEqual(result.stdout,'||x||next')

    def test_missing_native_dependency_is_reported(self):
        with self.assertRaisesRegex(ValueError,'libmissing'):
            parse_dependencies('libmissing.so.1 => not found\n')
        self.assertEqual(parse_dependencies('libtest.so.1 => /lib64/libtest.so.1 (0x123)\n/lib64/ld-linux.so.2 (0x123)'),
                         {'libtest.so.1':Path('/lib64/libtest.so.1')})

    def test_same_soname_with_different_bytes_is_not_silently_overwritten(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);a=root/'a';b=root/'b';a.write_bytes(b'first');b.write_bytes(b'second')
            target=root/'out/libtest.so.1';seen={}
            copy_runtime_file(a,target,seen)
            with self.assertRaisesRegex(ValueError,'collision'):copy_runtime_file(b,target,seen)
            self.assertEqual(target.read_bytes(),b'first')

    def test_vulkan_layer_library_is_relative_after_staging(self):
        source={'layer':{'name':'VK_LAYER_AFMF','library_path':'/old/build/libafmf-linux.so'}}
        result=portable_layer_manifest(source)
        self.assertEqual(result['layer']['library_path'],'./libafmf-linux.so')
        self.assertEqual(source['layer']['library_path'],'/old/build/libafmf-linux.so')

    def test_sdl_compat_runtime_includes_its_dynamically_loaded_sdl3(self):
        from tools.linux_runtime import dynamic_dependencies
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);sdl3=root/'libSDL3.so.0';sdl3.write_bytes(b'synthetic SDL3')
            result=dynamic_dependencies({'libSDL2-2.0.so.0':root/'libSDL2-2.0.so.0'},root)
            self.assertEqual(result,{'libSDL3.so.0':sdl3})
            sdl3.unlink()
            with self.assertRaisesRegex(ValueError,'SDL3'):dynamic_dependencies({'libSDL2-2.0.so.0':root/'SDL2'},root)

    def test_abi_floor_uses_import_requirements_not_exported_versions(self):
        from tools.linux_runtime import parse_glibc_requirements
        output = """Version definition section '.gnu.version_d' contains 1 entry:
 Name: GLIBC_2.99
Version needs section '.gnu.version_r' contains 1 entry:
 Name: GLIBC_2.34 Flags: none
 Name: GLIBC_ABI_DT_RELR Flags: none
 Name: GLIBCXX_3.4.32 Flags: none
"""
        self.assertEqual(parse_glibc_requirements(output), ['GLIBC_2.34', 'GLIBC_ABI_DT_RELR'])

    def test_abi_floor_accounts_for_non_numeric_dt_relr_requirement(self):
        from tools.linux_runtime import glibc_floor
        self.assertEqual(glibc_floor(['GLIBC_2.9', 'GLIBC_2.34', 'GLIBC_ABI_DT_RELR']), '2.36')
        self.assertEqual(glibc_floor(['GLIBC_2.9', 'GLIBC_2.38']), '2.38')
        with self.assertRaisesRegex(ValueError, 'Unknown glibc ABI'):
            glibc_floor(['GLIBC_ABI_UNKNOWN'])

    def test_wmv_profile_excludes_unrelated_camera_network_and_qt_plugins(self):
        from tools.linux_runtime import select_video_plugins
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            for name in ['libgstcoreelements.so','libgstlibav.so','libgstasf.so',
                         'libgstplayback.so','libgsttypefindfunctions.so',
                         'libgstaudioconvert.so','libgstaudioresample.so',
                         'libgstvideoconvertscale.so','libgstvideofilter.so',
                         'libgstdeinterlace.so','libgstqml6.so','libgstsoup.so']:
                (root/name).touch()
            selected=select_video_plugins(root,'wmv')
            self.assertEqual(len(selected),10)
            self.assertNotIn(root/'libgstqml6.so',selected)
            (root/'libgstasf.so').unlink()
            with self.assertRaisesRegex(ValueError,'libgstasf'):
                select_video_plugins(root,'wmv')

    def test_linux_preflight_rejects_old_glibc_before_loading_private_binaries(self):
        import os
        import subprocess
        guard=Path(__file__).resolve().parents[1]/'tools/check_linux_runtime.sh'
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            for name,body in [('getconf',"printf 'glibc 2.31\\n'"),('uname',"printf 'x86_64\\n'")]:
                path=root/name;path.write_text('#!/bin/sh\n'+body+'\n');path.chmod(0o755)
            env=dict(os.environ,PATH=str(root))
            result=subprocess.run(['/bin/sh',str(guard)],env=env,text=True,capture_output=True)
            self.assertEqual(result.returncode,1)
            self.assertIn('this system has 2.31',result.stderr)
            (root/'getconf').write_text("#!/bin/sh\nprintf 'glibc 2.42\\n'\n")
            self.assertEqual(subprocess.run(['/bin/sh',str(guard)],env=env).returncode,0)

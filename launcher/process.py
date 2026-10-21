"""Locking, reversible configuration and process lifetime. djultra64."""
from pathlib import Path
from contextlib import contextmanager
import os
import subprocess
import tempfile
import sys
from launcher.runtime import LaunchPlan, build_launch_plan, windows_graphics_enabled
from dataclasses import replace
from launcher.settings import Settings, apply_graphics, atomic_write, save_settings

@contextmanager
def _clean_dll_directory(kernel):
    import ctypes
    size=kernel.GetDllDirectoryW(0,None)
    previous=ctypes.create_unicode_buffer(size+1)
    if size:kernel.GetDllDirectoryW(size+1,previous)
    if not kernel.SetDllDirectoryW(None):
        raise OSError('Could not restore the Windows DLL search path for the game.')
    try:yield
    finally:
        if not kernel.SetDllDirectoryW(previous.value if size else None):
            raise OSError('Could not restore the launcher DLL search path.')

@contextmanager
def clean_windows_dll_search():
    # The PyInstaller bootloader adds its private CPython/Tk directory globally.
    # A native game child must resolve its own DLLs instead. Restore the launcher
    # directory immediately after process creation, while the child keeps a clean
    # inherited search configuration. Source and Linux launches are unaffected.
    if os.name=='nt' and getattr(sys,'frozen',False):
        import ctypes
        kernel=ctypes.WinDLL('kernel32',use_last_error=True)
        kernel.GetDllDirectoryW.argtypes=[ctypes.c_uint32,ctypes.c_wchar_p]
        kernel.GetDllDirectoryW.restype=ctypes.c_uint32
        kernel.SetDllDirectoryW.argtypes=[ctypes.c_wchar_p]
        kernel.SetDllDirectoryW.restype=ctypes.c_int
        with _clean_dll_directory(kernel):yield
    else:yield

@contextmanager
def prepared_launch(plan: LaunchPlan):
    if not plan.preload_libraries:
        yield plan
        return
    # Absolute paths are needed because Proton prepends its own library paths.
    # A short-lived, private alias also avoids glibc splitting spaces in paths.
    # Nothing is persisted outside the portable folder after the process exits.
    with tempfile.TemporaryDirectory(prefix='topspin-media-',dir='/tmp') as temp:
        alias=Path(temp)/'game';alias.symlink_to(plan.cwd,target_is_directory=True)
        preload=':'.join(str(alias/path.relative_to(plan.cwd)) for path in plan.preload_libraries)
        env=plan.env.copy()
        if 'LD_PRELOAD' in env:env['LD_PRELOAD']=preload
        argv=['LD_PRELOAD='+preload if arg.startswith('LD_PRELOAD=') else arg for arg in plan.argv]
        yield LaunchPlan(argv,plan.cwd,env,plan.preload_libraries)

class GameLock:
    def __init__(self,root):self.path=Path(root)/'.portable/game.lock';self.stream=None
    def __enter__(self):
        self.path.parent.mkdir(parents=True,exist_ok=True)
        self.stream=self.path.open('a+b')
        try:
            if os.name=='nt':
                import msvcrt
                self.stream.seek(0,2)
                if self.stream.tell()==0:self.stream.write(b'\0');self.stream.flush()
                self.stream.seek(0);msvcrt.locking(self.stream.fileno(),msvcrt.LK_NBLCK,1)
            else:
                import fcntl
                fcntl.flock(self.stream.fileno(),fcntl.LOCK_EX|fcntl.LOCK_NB)
        except OSError:
            self.stream.close();self.stream=None
            raise ValueError('Top Spin is already running from this folder.') from None
        return self
    def __exit__(self,*args):
        if self.stream:
            if os.name=='nt':
                import msvcrt
                self.stream.seek(0);msvcrt.locking(self.stream.fileno(),msvcrt.LK_UNLCK,1)
            else:
                import fcntl
                fcntl.flock(self.stream.fileno(),fcntl.LOCK_UN)
            self.stream.close();self.stream=None


def _save(root,settings):
    config=root/'Config.pml'
    original=config.read_bytes()
    graphics=None;graphics_original=None
    use_wrapper=sys.platform=='win32' and windows_graphics_enabled(root)
    if use_wrapper:
        from tools.windows_graphics import make_config
        graphics=root/'dgVoodoo.conf';graphics_original=graphics.read_bytes()
        graphics_changed=make_config(settings.internal_resolution,settings.output_resolution,
                                     fullscreen=False).encode('ascii')
    # The tested native path creates a real internal-size backbuffer and scales
    # it into our output-size window. Wrapper-only resolution overrides did not
    # create a 4K render target in the independent Windows GPU probe.
    game_settings=replace(settings,fullscreen=False) if use_wrapper else settings
    changed=apply_graphics(original,game_settings)
    if (root/'.portable/input.json').is_file():
        from launcher.controllers import profile_from_positions
        from tools.controller_config import remap_existing_controls
        changed=remap_existing_controls(changed,profile_from_positions(settings.menu_positions))
    updates={config:changed}
    if graphics is not None:updates[graphics]=graphics_changed
    if (root/'.portable/input.json').is_file():
        from launcher.glyphs import plan_prompt_style
        prompts=plan_prompt_style(root,settings.controller_family,settings.menu_positions)
        updates.update(prompts)
        if (root/'.portable/integrity.json').is_file() and prompts:
            import json
            from launcher.integrity import manifest_with_updates
            manifest=manifest_with_updates(root,prompts)
            updates[root/'.portable/integrity.json']=(json.dumps(manifest,indent=2)+'\n').encode()
    # Recoverable backup is created once; never overwrite an earlier user copy.
    backup=root/'.portable/Config.before-launcher.pml'
    if not backup.exists():atomic_write(backup,original)
    previous={path:path.read_bytes() if path.exists() else None for path in updates}
    preferences=root/'.portable/launcher.json'
    previous[preferences]=preferences.read_bytes() if preferences.exists() else None
    try:
        for path,payload in updates.items():atomic_write(path,payload)
        save_settings(root,settings)
    except Exception:
        for path,payload in previous.items():
            if payload is None:path.unlink(missing_ok=True)
            else:atomic_write(path,payload)
        raise
    return original


def save_configuration(root: Path,settings: Settings):
    with GameLock(root):_save(root,settings)


def run_game(root: Path,settings: Settings) -> int:
    # Resolve dependencies before changing game settings or creating a prefix.
    plan=build_launch_plan(root,settings)
    with GameLock(root):
        if 'STEAM_COMPAT_DATA_PATH' in plan.env:
            Path(plan.env['STEAM_COMPAT_DATA_PATH']).mkdir(parents=True,exist_ok=True)
        _save(root,settings)
        logs=root/'.portable/logs';logs.mkdir(parents=True,exist_ok=True)
        try:
            with prepared_launch(plan) as actual, (logs/'launch.log').open('wb') as stream:
                with clean_windows_dll_search():
                    process=subprocess.Popen(actual.argv,cwd=actual.cwd,env=actual.env,
                                             stdout=stream,stderr=subprocess.STDOUT)
                watcher=None
                if sys.platform=='win32' and windows_graphics_enabled(root):
                    from launcher.windows_display import start_window_watcher
                    watcher=start_window_watcher(process.pid,settings,logs/'windows-display.json')
                try:return process.wait()
                finally:
                    if watcher:
                        stop,worker=watcher;stop.set();worker.join(timeout=1)
        except OSError:
            # Saving is its own completed transaction. Keep preferences,
            # bindings, prompts and their manifest together if spawning fails.
            raise

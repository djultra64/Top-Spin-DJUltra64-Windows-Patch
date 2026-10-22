"""Build inspectable launch commands without starting a game. djultra64."""
from dataclasses import dataclass, field
from pathlib import Path
import json
import os
import sys
import re
from launcher.settings import Settings

@dataclass
class LaunchPlan:
    argv: list[str]
    cwd: Path
    env: dict[str,str]
    preload_libraries: list[Path] = field(default_factory=list)


def bundled_path(root: Path,value: str) -> Path:
    if not isinstance(value,str) or not value or Path(value).is_absolute():
        raise ValueError('Runtime paths must stay inside the portable folder.')
    result=(root/value).resolve()
    if not result.is_relative_to(root.resolve()):
        raise ValueError('Runtime paths must stay inside the portable folder.')
    return result

def windows_graphics_enabled(root: Path) -> bool:
    manifest=root/'.portable/windows-graphics.json'
    if not manifest.exists():return False
    try:
        data=json.loads(manifest.read_text())
        if (not isinstance(data,dict) or set(data)-{'version','backend','renderer'} or
                data.get('version')!=1 or data.get('backend')!='dgvoodoo2' or
                data.get('renderer','dgvoodoo2') not in {'dgvoodoo2','dxvk-afmf'}):
            raise ValueError('Unsupported Windows graphics runtime manifest.')
    except (OSError,json.JSONDecodeError) as exc:
        raise ValueError('Invalid Windows graphics runtime manifest.') from exc
    for name in ['d3d8.dll','dgVoodoo.conf']:
        if not bundled_path(root,name).is_file():
            raise ValueError('A Windows graphics runtime file is missing: '+name)
    return True


def steam_locations(environ: dict,platform: str) -> list[Path]:
    home=Path(environ.get('HOME',str(Path.home())))
    paths=[]
    if environ.get('STEAM_ROOT'):paths.append(Path(environ['STEAM_ROOT']))
    if platform=='win32':
        try:
            import winreg
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER,r'Software\Valve\Steam') as key:
                paths.append(Path(winreg.QueryValueEx(key,'SteamPath')[0]))
        except (ImportError,OSError):pass
        for key in ['ProgramFiles(x86)','ProgramFiles']:
            if environ.get(key):paths.append(Path(environ[key])/'Steam')
    else:
        paths.extend([home/'.local/share/Steam',home/'.steam/root',
                      home/'.var/app/com.valvesoftware.Steam/.local/share/Steam'])
    return list(dict.fromkeys(p.resolve() for p in paths if p.is_dir()))


def find_proton(root: Path,settings: Settings,environ: dict) -> Path | None:
    """Use the same Proton lookup for launching and the manual-picker fallback."""
    override=settings.proton_dir or environ.get('TOPSPIN_PROTON_DIR','')
    if override:
        candidate=Path(override)/'proton'
        return candidate if candidate.is_file() else None
    manifest=root/'.portable/runtime.json'
    runtime=json.loads(manifest.read_text()) if manifest.exists() else {}
    if not isinstance(runtime,dict):raise ValueError('Unsupported graphics runtime manifest.')
    if 'proton' in runtime:
        candidate=bundled_path(root,runtime['proton'])
        return candidate if candidate.is_file() else None
    for steam in steam_locations(environ,'linux'):
        for name in ['Proton 11.0','Proton - Experimental']:
            candidate=steam/'steamapps/common'/name/'proton'
            if candidate.is_file():return candidate
    return None


def capture_host_loader_environment(env,root,video_libraries=()):
    """Snapshot host settings before adding the private video/compositor stack."""
    private=(root/'runtime').resolve()
    def owned(value):
        path=Path(value)
        if not path.is_absolute():path=root/path
        return path.resolve().is_relative_to(private)
    libraries=[entry for entry in env.get('LD_LIBRARY_PATH','').split(':') if entry and not owned(entry)]
    preloads=[entry for entry in re.split(r'[:\s]+',env.get('LD_PRELOAD','')) if entry]
    video_names={path.name for path in video_libraries}
    preloads=[entry for entry in preloads if entry not in video_names and not owned(entry)]
    for key,values in [('LD_LIBRARY_PATH',libraries),('LD_PRELOAD',preloads)]:
        originally_set=key in env
        if values:env[key]=':'.join(values)
        elif originally_set and env[key]=='':env[key]=''
        else:env.pop(key,None)
        env['TOPSPIN_HOST_'+key+'_SET']='1' if key in env else '0'
        env['TOPSPIN_HOST_'+key]=env.get(key,'')


def build_launch_plan(root: Path,settings: Settings,*,platform=None,environ=None) -> LaunchPlan:
    root=root.resolve();platform=platform or sys.platform
    env=dict(os.environ if environ is None else environ)
    # The launcher's private interpreter must not replace Proton's interpreter
    # or leak its Tk libraries into the game/compositor environment.
    if env.get('PYTHONHOME')==str(root/'runtime/python'):
        for key in ['PYTHONHOME','PYTHONPATH','TK_LIBRARY','TCL_LIBRARY']:
            env.pop(key,None)
        private_lib=str(root/'runtime/python/lib64')
        libraries=[p for p in env.get('LD_LIBRARY_PATH','').split(':') if p and p!=private_lib]
        if libraries:env['LD_LIBRARY_PATH']=':'.join(libraries)
        else:env.pop('LD_LIBRARY_PATH',None)
    if not (root/'TopSpin.exe').is_file():raise ValueError('TopSpin.exe was not found in this folder.')
    input_manifest=root/'.portable/input.json'
    if input_manifest.exists():
        try:
            input_info=json.loads(input_manifest.read_text())
            if input_info!={'version':1,'glyph_count':48}:
                raise ValueError('Unsupported controller runtime manifest.')
        except (OSError,TypeError,json.JSONDecodeError) as exc:
            raise ValueError('Invalid controller runtime manifest.') from exc
        for name in ['djultra-input.dll','SDL3.dll']:
            path=bundled_path(root,'runtime/input/'+name)
            if not path.is_file():raise ValueError('A controller runtime file is missing: '+name)
        env.update(TOPSPIN_CONTROLLER_FAMILY=settings.controller_family,
                   TOPSPIN_STATIC_PROMPTS='0' if settings.controller_family=='auto' else '1',
                   TOPSPIN_MENU_POSITIONS=settings.menu_positions)
    elif settings.controller_family!='auto' or settings.menu_positions!='01234567':
        raise ValueError('The controller runtime is required for these controller settings.')
    if platform=='win32':
        from launcher.windows_framegen import configure_environment
        configure_environment(root,env,settings.frame_generation)
        graphics=windows_graphics_enabled(root)
        if settings.internal_resolution!=settings.output_resolution and not graphics:
            raise ValueError('Separate internal and output resolutions require the Windows graphics runtime.')
        return LaunchPlan([str(root/'TopSpin.exe')],root,env)
    if platform!='linux':raise ValueError('This launcher supports Windows and Linux.')
    manifest=root/'.portable/runtime.json'
    runtime=json.loads(manifest.read_text()) if manifest.exists() else {}
    allowed={'proton','gamescope','afmf_layer','video_libraries','video_plugins','library_path'}
    if not isinstance(runtime,dict) or set(runtime)-allowed:
        raise ValueError('Unsupported graphics runtime manifest.')
    resolved={}
    for key,value in runtime.items():
        if key=='video_libraries':
            if not isinstance(value,list):raise ValueError('Invalid video runtime.')
            resolved[key]=[bundled_path(root,v) for v in value]
        else:resolved[key]=bundled_path(root,value)
    # Validate all declared paths, including inactive options; a moved/incomplete
    # runtime must produce a useful error before attempting to run the game.
    for value in resolved.values():
        for path in value if isinstance(value,list) else [value]:
            if not path.exists():raise ValueError('A graphics runtime file is missing: '+str(path))
    # The tested Proton 11 path needs a coherent video stack; otherwise the
    # menu can show color bars even though the executable itself starts.
    if not resolved.get('video_libraries') or 'video_plugins' not in resolved:
        raise ValueError('Video playback runtime is missing. Install the Linux graphics runtime.')
    if settings.frame_generation and not {'gamescope','afmf_layer'}<=resolved.keys():
        raise ValueError('Frame generation requires the optional Linux graphics runtime.')
    if settings.frame_generation:
        layer_file=resolved['afmf_layer']/'afmf-linux.json'
        try:
            layer=json.loads(layer_file.read_text())['layer']
            library=layer['library_path']
            if layer['name']!='VK_LAYER_AFMF' or Path(library).is_absolute():
                raise ValueError('A portable frame generation layer requires a relative library path.')
            local=bundled_path(root,str((resolved['afmf_layer']/library).relative_to(root)))
            if not local.is_file():raise ValueError('The frame generation runtime library is missing.')
        except (OSError,KeyError,TypeError) as exc:
            raise ValueError('The frame generation runtime manifest is missing or invalid.') from exc
    if settings.internal_resolution!=settings.output_resolution and 'gamescope' not in resolved:
        raise ValueError('Separate internal and output resolutions require the Linux graphics runtime.')
    roots=steam_locations(env,platform)
    proton=find_proton(root,settings,env)
    if proton is None:
        raise ValueError('Proton was not found. Install Proton 11 through Steam or choose its folder.')
    steam=roots[0] if roots else Path(env.get('STEAM_COMPAT_CLIENT_INSTALL_PATH',''))
    if not steam.is_dir() or not roots and not env.get('STEAM_COMPAT_CLIENT_INSTALL_PATH'):
        raise ValueError('Steam was not found. Set STEAM_ROOT to its installation folder.')
    env.update(STEAM_COMPAT_DATA_PATH=str(root/'.portable/proton'),
               STEAM_COMPAT_CLIENT_INSTALL_PATH=str(steam),PROTON_USE_WOW64='1',
               PROTON_DXVK_D3D8='1',SteamAppId='0',SteamGameId='0',
               WINEDEBUG='-all',DXVK_LOG_PATH=str(root/'.portable/logs'),
               DXVK_CONFIG_FILE=str(root/'dxvk.conf'))
    capture_host_loader_environment(env,root,resolved.get('video_libraries',[]))
    library_dirs=[]
    if 'video_libraries' in resolved:
        libraries=resolved['video_libraries']
        names=[p.name for p in libraries]
        if any(any(c.isspace() or c==':' for c in name) for name in names) or len(set(names))!=len(names):
            raise ValueError('Video runtime library filenames must be unique and contain no spaces or colons.')
        # Unlike LD_LIBRARY_PATH, LD_PRELOAD also splits on whitespace. Use
        # basenames with an explicit search path so folders like "Top Spin" work.
        env['LD_PRELOAD']=':'.join(names)
        library_dirs.extend(str(p.parent) for p in libraries)
        env['GST_REGISTRY_FORK']='no'
        env['GST_REGISTRY_1_0']=str(root/'.portable/gstreamer-registry.bin')
    if 'video_plugins' in resolved:env['GST_PLUGIN_PATH_1_0']=str(resolved['video_plugins'])
    if 'library_path' in resolved:
        library_dirs.append(str(resolved['library_path']))
    if any(':' in path for path in library_dirs):
        raise ValueError('Linux video runtime folder paths cannot contain colons.')
    if library_dirs:
        env['LD_LIBRARY_PATH']=':'.join(dict.fromkeys(library_dirs))+(':'+env['LD_LIBRARY_PATH'] if env.get('LD_LIBRARY_PATH') else '')
    if settings.frame_generation:
        env.update(VK_ADD_IMPLICIT_LAYER_PATH=str(resolved['afmf_layer']),AFMF_ENABLE='1',
                   AFMF_LOG='2',AFMF_MIN_FPS='0',AFMF_GAMESCOPE='1')
    else:env['AFMF_ENABLE']='0'
    argv=[str(proton),'run',str(root/'TopSpin.exe')]
    if 'gamescope' in resolved:
        iw,ih=settings.internal_resolution.split('x');ow,oh=settings.output_resolution.split('x')
        child_values={key:env[key] for key in ['LD_PRELOAD','LD_LIBRARY_PATH','GST_REGISTRY_FORK','GST_REGISTRY_1_0',
             'GST_PLUGIN_PATH_1_0','VK_ADD_IMPLICIT_LAYER_PATH','AFMF_ENABLE','AFMF_LOG','AFMF_MIN_FPS','AFMF_GAMESCOPE'] if key in env}
        # Graphics overrides belong to the child game, not the compositor.
        for key in child_values:env.pop(key,None)
        argv=[str(resolved['gamescope']),'--backend','sdl','-w',iw,'-h',ih,'-W',ow,'-H',oh,
              '-r','120' if settings.frame_generation else '60']+(['-f'] if settings.fullscreen else [])+[
              '--','env']+[key+'='+value for key,value in child_values.items()]+argv
        env['SDL_VIDEODRIVER']='x11'
    return LaunchPlan(argv,root,env,preload_libraries=resolved.get('video_libraries',[]))

"""Stage the locally validated Linux graphics runtime with provenance. djultra64.

This stages host-built libraries, retaining their ABI floor. It does not claim
compatibility with older glibc distributions or bundle GPU vendor drivers.
"""
import argparse
import copy
import hashlib
import json
import re
import shutil
import subprocess
import os
import shlex
from pathlib import Path
from launcher.settings import atomic_write

GST_LIBS=['gstreamer','gstbase','gsttag','gstvideo','gstaudio','gstpbutils',
          'gstapp','gstgl','gstrtp','gstriff','gstrtsp','gstsdp']
GLIBC=re.compile(r'^(?:lib(?:c|m|mvec|dl|pthread|rt|resolv|util|anl|nss_[^.]*)\.so|ld-linux)')
# Drivers and the system Vulkan/GL dispatch stay with the installed GPU stack.
GPU=re.compile(r'^(?:libvulkan|libEGL|libGLX|libGLdispatch|libGL\.so|libnvidia|libcuda)')


def parse_glibc_requirements(output):
    """Read imported ABI versions, ignoring a library's exported versions."""
    needs = False
    versions = set()
    for line in output.splitlines():
        if line.startswith('Version needs section '):
            needs = True
        elif line.startswith('Version ') and ' section ' in line:
            needs = False
        if needs:
            versions.update(re.findall(r'\bName: (GLIBC_[A-Za-z0-9_.]+)', line))
    return sorted(versions)


def glibc_floor(requirements):
    versions = [(2, 2, 5)]
    for name in requirements:
        if re.fullmatch(r'GLIBC_\d+(?:\.\d+)+', name):
            versions.append(tuple(int(x) for x in name[6:].split('.')))
        elif name == 'GLIBC_ABI_DT_RELR':
            versions.append((2, 36))
        elif name in ('GLIBC_ABI_GNU2_TLS', 'GLIBC_ABI_DT_X86_64_PLT'):
            # Backported to selected 2.41 distributions; 2.42 is the safe
            # unpatched baseline. Retain exact tags in the audit as well.
            versions.append((2, 42))
        else:
            raise ValueError('Unknown glibc ABI requirement: ' + name)
    return '.'.join(map(str, max(versions)))


def audit_abi(root):
    """Inspect ELF imports without loading or running bundled executables."""
    root = Path(root).resolve()
    files = {}
    requirements = set()
    for path in sorted(root.rglob('*')):
        if not path.is_file() or path.is_symlink():
            continue
        with path.open('rb') as stream:
            if stream.read(4) != b'\x7fELF':
                continue
        result = subprocess.run(['readelf', '--version-info', str(path)],
                                check=True, capture_output=True, text=True)
        imported = parse_glibc_requirements(result.stdout)
        requirements.update(imported)
        files[str(path.relative_to(root))] = {
            'minimum_glibc': glibc_floor(imported),
            'required_glibc_versions': imported,
        }
    return {'author': 'djultra64', 'architecture': 'x86_64',
            'minimum_glibc': glibc_floor(requirements), 'elf_files': files,
            'scope': 'Static ABI requirements only; GPU drivers, display and gameplay need separate validation.'}


def parse_dependencies(output):
    result={}
    for line in output.splitlines():
        match=re.match(r'\s*(\S+)\s+=>\s+(.*)',line)
        if not match:continue
        name,target=match.groups()
        if target.startswith('not found'):raise ValueError('Missing native dependency: '+name)
        path=target.rsplit(' (',1)[0]
        if path.startswith('/'):result[name]=Path(path)
    return result



def dynamic_dependencies(dependencies,library_dir=Path('/usr/lib64')):
    # Fedora's SDL2 SONAME is sdl2-compat, which dlopens SDL3 rather than listing
    # it in DT_NEEDED. ldd alone therefore misses this runtime dependency.
    result={}
    if 'libSDL2-2.0.so.0' in dependencies:
        path=library_dir/'libSDL3.so.0'
        if not path.is_file():raise ValueError('Missing dynamic SDL3 runtime dependency: '+str(path))
        result[path.name]=path
    return result


def copy_runtime_file(source,target,seen):
    digest=hashlib.sha256(source.read_bytes()).hexdigest()
    key=str(target)
    if key in seen and seen[key]['sha256']!=digest:
        raise ValueError('Native library collision: '+target.name)
    if key not in seen:
        target.parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(source.resolve(),target)
        seen[key]={'sha256':digest,'source':str(source.resolve()),'size':source.stat().st_size}


def portable_layer_manifest(source):
    result=copy.deepcopy(source)
    if result['layer']['name']!='VK_LAYER_AFMF':raise ValueError('Unexpected Vulkan layer')
    result['layer']['library_path']='./libafmf-linux.so'
    return result


WMV_PLUGINS = ('coreelements', 'typefindfunctions', 'playback', 'asf', 'libav',
               'audioconvert', 'audioresample', 'videoconvertscale',
               'videofilter', 'deinterlace')


def select_video_plugins(directory, profile='all'):
    directory = Path(directory)
    if profile == 'all':
        return sorted(directory.glob('*.so'))
    if profile != 'wmv':
        raise ValueError('Unknown video plugin profile: ' + profile)
    selected = [directory / ('libgst' + name + '.so') for name in WMV_PLUGINS]
    for path in selected:
        if not path.is_file():
            raise ValueError('Missing WMV video plugin: ' + str(path))
    return selected


def gamescope_wrapper():
    return '''#!/bin/sh
# djultra64: compositor and Xwayland resolve their bundled dependencies locally.
rt="$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd -P)"
if [ ! -f "$rt/bin/Xwayland" ] || [ ! -x "$rt/bin/Xwayland" ]; then
    printf '%s\\n' 'The bundled Xwayland executable is missing or not executable. Check game files for integrity.' >&2
    exit 1
fi
for helper in gamescopereaper zenity; do
    if [ ! -f "$rt/bin/$helper" ] || [ ! -x "$rt/bin/$helper" ]; then
        printf '%s\\n' "The bundled $helper helper is missing or not executable. Check game files for integrity." >&2
        exit 1
    fi
done
# A direct wrapper invocation also needs a clean snapshot before adding libs.
if [ -z "${TOPSPIN_HOST_LD_LIBRARY_PATH_SET+x}" ]; then
    if [ "${LD_LIBRARY_PATH+x}" = x ]; then
        TOPSPIN_HOST_LD_LIBRARY_PATH_SET=1
        TOPSPIN_HOST_LD_LIBRARY_PATH="$LD_LIBRARY_PATH"
    else
        TOPSPIN_HOST_LD_LIBRARY_PATH_SET=0
        TOPSPIN_HOST_LD_LIBRARY_PATH=
    fi
    export TOPSPIN_HOST_LD_LIBRARY_PATH_SET TOPSPIN_HOST_LD_LIBRARY_PATH
fi
if [ -z "${TOPSPIN_HOST_LD_PRELOAD_SET+x}" ]; then
    if [ "${LD_PRELOAD+x}" = x ]; then
        TOPSPIN_HOST_LD_PRELOAD_SET=1
        TOPSPIN_HOST_LD_PRELOAD="$LD_PRELOAD"
    else
        TOPSPIN_HOST_LD_PRELOAD_SET=0
        TOPSPIN_HOST_LD_PRELOAD=
    fi
    export TOPSPIN_HOST_LD_PRELOAD_SET TOPSPIN_HOST_LD_PRELOAD
fi
export PATH="$rt/bin${PATH:+:$PATH}"
export LD_LIBRARY_PATH="$rt/lib64${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
export WLR_XWAYLAND="$rt/bin/Xwayland"
export GAMESCOPE_SCRIPT_PATH="$rt/share/gamescope/scripts"
export XKB_CONFIG_ROOT="$rt/share/X11/xkb"
"$rt/check-abi.sh" || exit $?
exec "$rt/bin/gamescope.bin" "$@"
'''


def host_zenity_wrapper(executable=Path('/usr/bin/zenity')):
    """Run the actual host dialog with its host loader environment restored."""
    executable=Path(executable)
    if not executable.is_absolute():raise ValueError('The host zenity path must be absolute.')
    return '''#!/bin/sh
# djultra64: host GTK/GStreamer must not load the game's private runtime.
if [ "${TOPSPIN_HOST_LD_LIBRARY_PATH_SET:-0}" = 1 ]; then
    export LD_LIBRARY_PATH="${TOPSPIN_HOST_LD_LIBRARY_PATH-}"
else
    unset LD_LIBRARY_PATH
fi
if [ "${TOPSPIN_HOST_LD_PRELOAD_SET:-0}" = 1 ]; then
    export LD_PRELOAD="${TOPSPIN_HOST_LD_PRELOAD-}"
else
    unset LD_PRELOAD
fi
exec '''+shlex.quote(str(executable))+''' "$@"
'''


def stage(game: Path,afmf: Path,video_profile='all',*,reaper: Path|None=None):
    game=game.resolve();afmf=afmf.resolve()
    if not (game/'TopSpin.exe').is_file():raise ValueError('Choose an extracted game folder')
    target=game/'runtime/linux';seen={}
    reaper=Path(reaper) if reaper is not None else Path('/usr/bin/gamescopereaper')
    seeds=[Path('/usr/bin/gamescope'),Path('/usr/bin/Xwayland'),reaper]
    plugins=select_video_plugins(Path('/usr/lib64/gstreamer-1.0'),video_profile)
    libraries=[Path('/usr/lib64')/('lib'+name+'-1.0.so.0') for name in GST_LIBS]
    for source in seeds+plugins+libraries+[afmf/'libafmf-linux.so']:
        if not source.is_file():raise ValueError('Runtime input missing: '+str(source))
    for source in seeds:
        if not os.access(source,os.X_OK):raise ValueError('Runtime executable input is not executable: '+str(source))
    for source,name in zip(seeds,['gamescope.bin','Xwayland','gamescopereaper']):
        copy_runtime_file(source,target/'bin'/name,seen)
    for source in plugins:copy_runtime_file(source,target/'gstreamer-1.0'/source.name,seen)
    for source in libraries:copy_runtime_file(source,target/'lib64'/source.name,seen)
    # Proton's WMV path additionally needs the older SONAME shipped by Sniper.
    compat=Path('build/deps/video64/libbz2.so.1.0')
    if not compat.is_file():raise ValueError('Missing Proton video compatibility input: '+str(compat))
    copy_runtime_file(compat,target/'lib64/libbz2.so.1.0',seen)
    dependencies={}
    for source in seeds+plugins+libraries+[afmf/'libafmf-linux.so']:
        output=subprocess.run(['ldd',str(source)],check=True,capture_output=True,text=True).stdout
        dependencies.update(parse_dependencies(output))
    dynamic=dynamic_dependencies(dependencies)
    dependencies.update(dynamic)
    for source in dynamic.values():
        output=subprocess.run(['ldd',str(source)],check=True,capture_output=True,text=True).stdout
        dependencies.update(parse_dependencies(output))
    external={}
    for name,source in sorted(dependencies.items()):
        if GLIBC.match(name) or GPU.match(name):external[name]=str(source);continue
        copy_runtime_file(source,target/'lib64'/name,seen)
    copy_runtime_file(afmf/'libafmf-linux.so',target/'afmf/libafmf-linux.so',seen)
    layer=portable_layer_manifest(json.loads((afmf/'afmf-linux.json').read_text()))
    atomic_write(target/'afmf/afmf-linux.json',(json.dumps(layer,indent=2)+'\n').encode())
    shutil.copytree('/usr/share/gamescope',target/'share/gamescope',dirs_exist_ok=True)
    shutil.copytree('/usr/share/X11/xkb',target/'share/X11/xkb',dirs_exist_ok=True)
    wrapper=gamescope_wrapper()
    (target/'bin/gamescope').write_text(wrapper);(target/'bin/gamescope').chmod(0o755)
    (target/'bin/zenity').write_text(host_zenity_wrapper());(target/'bin/zenity').chmod(0o755)
    guard=Path(__file__).with_name('check_linux_runtime.sh')
    shutil.copy2(guard,target/'check-abi.sh')
    # Keep installed-package license/copyright notices and exact package/source
    # provenance. This local stage is not a substitute for a public source release.
    packages={}
    for item in seen.values():
        query=subprocess.run(['rpm','-qf','--qf','%{NAME}|%{VERSION}-%{RELEASE}|%{LICENSE}|%{SOURCERPM}',item['source']],
                             capture_output=True,text=True)
        if query.returncode:continue
        fields=query.stdout.split('|')
        if len(fields)==4:packages[fields[0]]=fields[1:]
    for package in packages:
        files=subprocess.run(['rpm','-ql',package],check=True,capture_output=True,text=True).stdout.splitlines()
        for name in files:
            path=Path(name)
            if path.is_file() and name.startswith('/usr/share/') and any(
                    word in path.name.lower() for word in ['license','copying','copyright','notice']):
                copy_runtime_file(path,target/'licenses'/package/path.name,seen)
    notices=Path('build/third-party/afmf-linux/unpacked/afmf-linux-1.3.1')
    for name in ['LICENSE','LICENSE.fidelityfx.txt','NOTICE.fidelityfx.md']:
        copy_runtime_file(notices/name,target/'licenses/afmf-linux'/name,seen)
    steam=compat.resolve()
    files=next((parent for parent in steam.parents if parent.name=='files'),None)
    if files is not None:
        notice=files/'share/doc/libbz2-1.0/copyright'
        if notice.is_file():copy_runtime_file(notice,target/'licenses/bzip2/copyright',seen)
    manifest={'gamescope':'runtime/linux/bin/gamescope','afmf_layer':'runtime/linux/afmf',
              'video_libraries':['runtime/linux/lib64/lib'+n+'-1.0.so.0' for n in GST_LIBS],
              'video_plugins':'runtime/linux/gstreamer-1.0','library_path':'runtime/linux/lib64'}
    provenance={'author':'djultra64','status':'local-build-pending-integration-validation',
                'host_glibc':subprocess.run(['getconf','GNU_LIBC_VERSION'],capture_output=True,text=True,check=True).stdout.strip(),
                'video_profile':video_profile,
                'packages':packages,'external_system_libraries':external,
                'abi':audit_abi(target),
                'files':{str(Path(path).relative_to(game)):v for path,v in seen.items()}}
    atomic_write(target/'provenance.json',(json.dumps(provenance,indent=2)+'\n').encode())
    atomic_write(game/'.portable/runtime.json',(json.dumps(manifest,indent=2)+'\n').encode())
    return {'files':len(seen),'bytes':sum(v['size'] for v in seen.values()),'runtime':str(target)}

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('game',type=Path)
    parser.add_argument('--afmf',type=Path,default=Path('build/afmf64/layer'))
    parser.add_argument('--video-profile',choices=['all','wmv'],default='all')
    parser.add_argument('--reaper',type=Path,help='Matching gamescopereaper from the compositor build')
    args=parser.parse_args();print(json.dumps(stage(args.game,args.afmf,args.video_profile,reaper=args.reaper),indent=2))

"""Portable launcher settings, distinct from original game options. djultra64."""
from dataclasses import asdict, dataclass, fields
from pathlib import Path
import json
import os
import struct
import tempfile
from tools.pml import Pml
from launcher.controllers import FAMILIES

RESOLUTIONS=('1280x720','1600x900','1920x1080','2560x1440','3840x2160')

@dataclass(frozen=True)
class Settings:
    internal_resolution: str='1920x1080'
    output_resolution: str='1920x1080'
    fullscreen: bool=True
    frame_generation: bool=False
    proton_dir: str=''
    controller_family: str='auto'
    menu_positions: str='01234567'

    def __post_init__(self):
        if self.controller_family not in ('auto','keyboard')+FAMILIES:
            raise ValueError('Choose Keyboard, Auto or a supported controller family.')
        if not isinstance(self.menu_positions,str) or len(self.menu_positions)!=8 or any(c not in '01234567' for c in self.menu_positions):
            raise ValueError('Menu controls must use eight physical button positions.')
        for name in ['internal_resolution','output_resolution']:
            if getattr(self,name) not in RESOLUTIONS:
                raise ValueError('Choose a supported 16:9 resolution.')
        if type(self.fullscreen) is not bool or type(self.frame_generation) is not bool:
            raise ValueError('Graphics switches must be true or false.')
        if not isinstance(self.proton_dir,str) or '\0' in self.proton_dir:
            raise ValueError('Invalid Proton location.')

    @classmethod
    def from_dict(cls,data):
        if not isinstance(data,dict) or set(data)-{f.name for f in fields(cls)}:
            raise ValueError('Unsupported launcher settings.')
        return cls(**data)


def atomic_write(path: Path,data: bytes):
    path.parent.mkdir(parents=True,exist_ok=True)
    fd,name=tempfile.mkstemp(prefix=path.name+'.',suffix='.tmp',dir=path.parent)
    try:
        with os.fdopen(fd,'wb') as stream:
            stream.write(data);stream.flush();os.fsync(stream.fileno())
        os.replace(name,path)
    finally:
        if os.path.exists(name):os.unlink(name)


def load_settings(root: Path) -> Settings:
    path=root/'.portable/launcher.json'
    if path.exists():return Settings.from_dict(json.loads(path.read_text()))
    config=root/'Config.pml'
    if not config.exists():return Settings()
    try:
        pml=Pml(config.read_bytes())
        resolution=pml.get('Video','Res_X')+'x'+pml.get('Video','Res_Y')
        positions='01234567'
        if (root/'.portable/input.json').is_file():
            from tools.controller_config import read_existing_menu_positions
            positions=read_existing_menu_positions(config.read_bytes())
        return Settings(menu_positions=positions,internal_resolution=resolution if resolution in RESOLUTIONS else '1920x1080',
                        fullscreen=pml.get('Video','FullScreen').lower()=='true')
    except (struct.error,KeyError,StopIteration,ValueError) as exc:
        raise ValueError('Config.pml is damaged or incompatible. The original file was left unchanged.') from exc


def save_settings(root: Path,settings: Settings):
    atomic_write(root/'.portable/launcher.json',
                 (json.dumps(asdict(settings),indent=2)+'\n').encode())


def apply_graphics(raw: bytes,settings: Settings) -> bytes:
    try:
        config=Pml(raw);width,height=settings.internal_resolution.split('x')
        for section,key,value in [('Video','Res_X',width),('Video','Res_Y',height),
                 ('Video','FullScreen',str(settings.fullscreen).lower()),
                 ('Video','RefreshRate','50'),('DebugSettings','AutoSynchronize','true')]:
            config.set(section,key,value)
    except (struct.error,KeyError,StopIteration,ValueError) as exc:
        raise ValueError('Config.pml is damaged or incompatible. The original file was left unchanged.') from exc
    return config.encode()

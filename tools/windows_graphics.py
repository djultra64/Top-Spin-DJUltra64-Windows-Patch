"""Stage unmodified game-specific dgVoodoo2 components for Windows. djultra64.

Native Windows validation is required before claiming the forced resolution /
output combination works in a particular game. This module never launches one.
"""
from pathlib import Path
import hashlib
import json
import re
import zipfile

VERSION='2.87.5'
SOURCE_URL='https://github.com/dege-diosg/dgVoodoo2/releases/download/v2.87.5/dgVoodoo2_87_5.zip'
ARCHIVE_SHA256='5ffde6927f7355ca3fdd5d785b581256a8e6539fa13e395a891ade6ba1040850'
DLL_SHA256='d03e2562178db1fcf3493fc0a0b23a465e35c55d73adb3ec095be866cd662704'
README_URL='https://dege.freeweb.hu/dgVoodoo2/ReadmeGeneral/'


def _resolution(value):
    if not isinstance(value,str) or not re.fullmatch(r'[0-9]{3,4}x[0-9]{3,4}',value):
        raise ValueError('Choose a supported 16:9 resolution')
    width,height=map(int,value.split('x'))
    if width<640 or height<360 or width>7680 or height>4320 or width*9!=height*16:
        raise ValueError('Choose a supported 16:9 resolution')
    return value


def make_config(internal_resolution,output_resolution,*,fullscreen=True):
    internal=_resolution(internal_resolution);output=_resolution(output_resolution)
    # Top Spin filters enumerated modes against its requested render size even
    # in windowed mode. Expose that size when it exceeds the physical display.
    enumerated=', '.join(dict.fromkeys((internal,output)))
    if type(fullscreen) is not bool:raise ValueError('Invalid fullscreen choice')
    return f'''; Top Spin-specific Windows compatibility configuration. djultra64.
; dgVoodoo2 original components by Dege. See runtime/windows/licenses.
; No refresh override, frame limiter, or game simulation change.
Version = 0x287

[General]
OutputAPI = d3d11_fl11_0
Adapters = all
FullScreenOutput = default
FullScreenMode = {str(fullscreen).lower()}
ScalingMode = stretched_ar
ProgressiveScanlineOrder = false
EnumerateRefreshRates = false
KeepWindowAspectRatio = true
CaptureMouse = true
CenterAppWindow = true

[GeneralExt]
DesktopResolution = {output}
Resampling = bilinear
PresentationModel = flip_discard
ColorSpace = argb8888_sdr
FullscreenAttributes = fake
FPSLimit = 0

[DirectX]
DisableAndPassThru = false
VideoCard = internal3D
VRAM = 256
Filtering = appdriven
Mipmapping = appdriven
Resolution = {internal}
Antialiasing = appdriven
AppControlledScreenMode = false
DisableAltEnterToToggleScreenMode = true
ForceVerticalSync = false
dgVoodooWatermark = false
DisableD3DTnLDevice = false

[DirectXExt]
DefaultEnumeratedResolutions = all
ExtraEnumeratedResolutions = {enumerated}
EnumeratedResolutionBitdepths = all
MaxVSConstRegisters = 256
D3D12BoundsChecking = true
AlternativeScaling = false
RTTexturesForceScaleAndMSAA = true
'''


def stage_dgvoodoo(destination,archive,readme,*,internal_resolution='3840x2160',
                   output_resolution='1920x1080',fullscreen=True):
    destination=Path(destination);archive=Path(archive);readme=Path(readme)
    config=make_config(internal_resolution,output_resolution,fullscreen=fullscreen)
    raw=archive.read_bytes()
    if hashlib.sha256(raw).hexdigest()!=ARCHIVE_SHA256:raise ValueError('Unrecognized dgVoodoo archive hash')
    with zipfile.ZipFile(archive) as source:
        dll=source.read('MS/x86/D3D8.dll')
    if hashlib.sha256(dll).hexdigest()!=DLL_SHA256:raise ValueError('Unrecognized dgVoodoo x86 DLL hash')
    notice=readme.read_bytes()
    if b'Redistribution rights' not in notice or b'game mod' not in notice:
        raise ValueError('Original dgVoodoo redistribution documentation is required')
    license_dir=destination/'runtime/windows/licenses/dgVoodoo2';license_dir.mkdir(parents=True,exist_ok=True)
    (destination/'d3d8.dll').write_bytes(dll)
    (destination/'dgVoodoo.conf').write_text(config,encoding='ascii')
    (destination/'.portable').mkdir(exist_ok=True)
    (destination/'.portable/windows-graphics.json').write_text(json.dumps({'version':1,'backend':'dgvoodoo2'})+'\n')
    (license_dir/'ReadmeGeneral.html').write_bytes(notice)
    provenance={'component':'dgVoodoo2','version':VERSION,'author':'Dege',
                'source':SOURCE_URL,'archive_sha256':ARCHIVE_SHA256,
                'original_entry':'MS/x86/D3D8.dll','sha256':DLL_SHA256,
                'license_source':README_URL,
                'scope':'Unmodified individual component supplied with this specific Top Spin mod.',
                'validation':'Native Windows device/presentation and game validation pending.'}
    (license_dir/'provenance.json').write_text(json.dumps(provenance,indent=2)+'\n')
    return provenance

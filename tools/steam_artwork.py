"""Stage user-supplied SteamGridDB artwork privately at build time. djultra64.

Downloaded artwork is not our original work and no public redistribution rights
are asserted. Only generated ignored build folders receive these image files.
Pillow is needed here, never by the runtime launcher.
"""
from pathlib import Path
import argparse
import hashlib
import io
import json
import urllib.request
from PIL import Image, UnidentifiedImageError
from launcher.settings import atomic_write
from launcher.steam_artwork import _png_size

ARTWORK_URLS={
 'icon':'https://cdn2.steamgriddb.com/icon/d3257767e94c24d25f618f96a324c780.png',
 'logo':'https://cdn2.steamgriddb.com/logo/e58226fbcc883887b380d916b41c4b0e.png',
 'hero':'https://cdn2.steamgriddb.com/hero/fbe0452c6aaf5ae4f65cc802298f9693.png',
 'grid_a':'https://cdn2.steamgriddb.com/grid/5b2abbcf7c45a21a72be22e15ef5f939.png',
 'grid_b':'https://cdn2.steamgriddb.com/grid/f5e4f9a607bd4a71fa49cb956af7ed78.png',
}


def fetch_image(url):
    request=urllib.request.Request(url,headers={'User-Agent':'TopSpinPortableArtwork/1.0'})
    with urllib.request.urlopen(request,timeout=30) as response:
        data=response.read(20*1024*1024+1)
    if len(data)>20*1024*1024:raise ValueError('The supplied artwork image is too large.')
    return data


def _derivative(raw,bounds,format='PNG'):
    with Image.open(io.BytesIO(raw)) as original:
        image=original.convert('RGBA');image.thumbnail(bounds,Image.Resampling.LANCZOS)
        stream=io.BytesIO()
        if format=='ICO':image.save(stream,format='ICO',sizes=[(n,n) for n in [16,24,32,48,64,128,256] if n<=max(image.size)])
        else:image.save(stream,format='PNG')
        return stream.getvalue()


def stage_artwork(destination,*,fetch=None):
    destination=Path(destination).resolve()
    private_build=Path(__file__).resolve().parents[1]/'build'
    if fetch is None and not destination.is_relative_to(private_build.resolve()):
        raise ValueError('Download supplied artwork only into the private build folder.')
    fetch=fetch or fetch_image
    inputs={role:fetch(url) for role,url in ARTWORK_URLS.items()};sizes={}
    for role,raw in inputs.items():
        sizes[role]=_png_size(raw)
        try:
            with Image.open(io.BytesIO(raw)) as image:image.verify()
        except (UnidentifiedImageError,OSError,SyntaxError) as exc:raise ValueError('Invalid supplied artwork image: '+role) from exc
    grids={}
    for name in ['grid_a','grid_b']:
        width,height=sizes[name]
        role='portrait' if height>width else 'landscape' if width>height else None
        if role is None or role in grids:raise ValueError('Supply one portrait cover and one landscape cover.')
        grids[role]=name
    output={role+'.png':inputs[name] for role,name in grids.items()}
    for role in ['icon','logo','hero']:output[role+'.png']=inputs[role]
    output['icon.ico']=_derivative(inputs['icon'],(256,256),'ICO')
    output['logo-launcher.png']=_derivative(inputs['logo'],(320,48))
    output['icon-launcher.png']=_derivative(inputs['icon'],(64,64))
    report={'version':1,'integration_author':'djultra64',
            'artwork_credit':'User-supplied SteamGridDB artwork. Original rights remain with their respective owners.',
            'redistribution_status':'No public redistribution rights established.',
            'sources':[{'role':next((role for role,name in grids.items() if name==key),key),'url':ARTWORK_URLS[key],
                        'sha256':hashlib.sha256(raw).hexdigest(),'width':sizes[key][0],'height':sizes[key][1]} for key,raw in inputs.items()],
            'derived':{name:{'sha256':hashlib.sha256(raw).hexdigest(),'operation':'Build-time image resizing / format conversion; original artwork design preserved.'} for name,raw in output.items() if name in ['icon.ico','logo-launcher.png','icon-launcher.png']}}
    output['sources.json']=(json.dumps(report,indent=2)+'\n').encode()
    directory=destination/'artwork/steam'
    if directory.is_symlink():raise ValueError('Artwork staging directory cannot be a symbolic link.')
    for name,raw in output.items():atomic_write(directory/name,raw)
    return report


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('destination',nargs='?',type=Path,default=Path('build/Steam-Artwork-Staging'))
    args=parser.parse_args();print(json.dumps(stage_artwork(args.destination),indent=2))

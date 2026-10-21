"""Extend a user's own font atlas with selected CC0 Xelu icons. djultra64.

No original glyph pixels are included in this source. The original DXT5 blocks
are preserved verbatim. Only UV coordinates change to account for added rows.
Controller artwork remains attributed to Xelu; its original PNGs and readme are
retained in assets/input/xelu. The game's existing compressed pixels stay intact.
"""
from dataclasses import dataclass
import math
import json
from pathlib import Path
from functools import lru_cache
import struct
from launcher.controllers import FAMILIES,DI_TOKENS

BASE_CODE=0xe000
ICON_COUNT=len(FAMILIES)*8

@dataclass
class Font:
    width: int
    height: int
    ranges: list[tuple[int,int]]
    codes: list[int]
    glyphs: list[bytes]


def parse_font(data):
    if len(data)<28:raise ValueError('Truncated font header.')
    version,line,width,height,ascent,count=struct.unpack_from('<6I',data)
    if (version!=6 or width not in (128,256,512) or height not in (256,512,1024,2048)
            or not 0<count<512 or not 1<=line<=128):
        raise ValueError('Unsupported font format.')
    if 28+count*4>len(data):raise ValueError('Truncated font ranges.')
    ranges=[struct.unpack_from('<HH',data,24+i*4) for i in range(count)]
    if any(lo>hi or (i and lo<=ranges[i-1][1]) for i,(lo,hi) in enumerate(ranges)):
        raise ValueError('Invalid font ranges.')
    codes=[code for lo,hi in ranges for code in range(lo,hi+1)]
    glyph_count=struct.unpack_from('<I',data,24+count*4)[0];start=28+count*4
    if glyph_count!=len(codes) or start+28*glyph_count!=len(data):
        raise ValueError('Font glyph table has an invalid size.')
    glyphs=[data[start+i*28:start+(i+1)*28] for i in range(glyph_count)]
    for glyph in glyphs:
        uv=struct.unpack_from('<4f',glyph)
        if not all(math.isfinite(v) and 0<=v<=1 for v in uv) or uv[0]>uv[2] or uv[1]>uv[3]:
            raise ValueError('Invalid font texture coordinates.')
    return Font(width,height,ranges,codes,glyphs)

ASSETS=Path(__file__).resolve().parent.parent/'assets/input/xelu'

@lru_cache(maxsize=64)
def icon_rgba(family,position):
    from PIL import Image
    if family not in FAMILIES or not 0<=position<8:raise ValueError('Unknown controller icon.')
    mapping=json.loads((ASSETS/'mapping.json').read_text())
    source=(ASSETS/mapping[family][tuple(DI_TOKENS)[position]]).resolve()
    if not source.is_relative_to(ASSETS.resolve()):raise ValueError('Icon path escapes its assets folder.')
    with Image.open(source) as original:
        rgba=original.convert('RGBA');bounds=rgba.getchannel('A').getbbox()
        if not bounds:raise ValueError('Empty controller icon.')
        rgba=rgba.crop(bounds)
        scale=min(23/rgba.width,20/rgba.height)
        rgba=rgba.resize((max(1,round(rgba.width*scale)),max(1,round(rgba.height*scale))),Image.Resampling.LANCZOS)
        canvas=Image.new('RGBA',(24,21));canvas.paste(rgba,((24-rgba.width)//2,(21-rgba.height)//2))
        return canvas.tobytes()


def encode_dxt5(rgba,width,height):
    if width%4 or height%4 or len(rgba)!=width*height*4:raise ValueError('Invalid icon canvas.')
    alpha_palette=[255,0]+[(255*(7-i))//7 for i in range(1,7)]
    def rgb565(rgb):return (rgb[0]>>3)<<11|(rgb[1]>>2)<<5|rgb[2]>>3
    def unpack(value):return ((value>>11)*255//31,((value>>5)&63)*255//63,(value&31)*255//31)
    def distance(a,b):return sum((x-y)**2 for x,y in zip(a,b))
    output=bytearray()
    for y in range(0,height,4):
        for x in range(0,width,4):
            pixels=[rgba[((y+i//4)*width+x+i%4)*4:((y+i//4)*width+x+i%4)*4+4] for i in range(16)]
            visible=[p[:3] for p in pixels if p[3]>16]
            if not visible:
                output.extend(bytes(16));continue
            c0,c1=max(((a,b) for a in visible for b in visible),key=lambda pair:distance(*pair))
            v0,v1=sorted((rgb565(c0),rgb565(c1)),reverse=True)
            a,b=unpack(v0),unpack(v1)
            colors=[a,b,tuple((2*a[i]+b[i])//3 for i in range(3)),tuple((a[i]+2*b[i])//3 for i in range(3))]
            alpha_bits=color_bits=0
            for i,pixel in enumerate(pixels):
                alpha_index=min(range(8),key=lambda j:abs(alpha_palette[j]-pixel[3]))
                color_index=min(range(4),key=lambda j:distance(colors[j],pixel[:3]))
                alpha_bits|=alpha_index<<(i*3);color_bits|=color_index<<(i*2)
            output.extend(bytes([255,0])+alpha_bits.to_bytes(6,'little')+struct.pack('<HHI',v0,v1,color_bits))
    return bytes(output)


def encode_dxt3(rgba,width,height):
    """DXT3 has explicit four-bit alpha; reuse the DXT5 RGB block encoder."""
    encoded=encode_dxt5(rgba,width,height);result=bytearray();block=0
    for y in range(0,height,4):
        for x in range(0,width,4):
            alpha=0
            for i in range(16):
                value=rgba[((y+i//4)*width+x+i%4)*4+3]
                alpha|=((value+8)//17)<<(i*4)
            result.extend(alpha.to_bytes(8,'little'))
            result.extend(encoded[block+8:block+16]);block+=16
    return bytes(result)


def extend_font(abc,dds):
    from PIL import Image
    font=parse_font(abc)
    if font.height>1024 or any(c>=BASE_CODE for c in font.codes):
        raise ValueError('Font is already extended or incompatible.')
    width,height=font.width,font.height
    if (len(dds)<128 or dds[:4]!=b'DDS ' or struct.unpack_from('<I',dds,4)[0]!=124
            or struct.unpack_from('<II',dds,12)!=(height,width)
            or struct.unpack_from('<I',dds,28)[0]>1):
        raise ValueError('Expected a matching single-level DDS font atlas.')
    fmt=dds[84:88]
    if fmt in (b'DXT3',b'DXT5'):
        if len(dds)!=128+width*height:
            raise ValueError('Truncated compressed DDS font atlas.')
    elif (struct.unpack_from('<7I',dds,76)==(32,65,0,32,0xff0000,0xff00,0xff)
            and struct.unpack_from('<I',dds,104)[0]==0xff000000):
        fmt=b'BGRA'
        if len(dds)!=128+width*height*4:raise ValueError('Truncated BGRA font atlas.')
    else:
        raise ValueError('Expected DXT3, DXT5 or BGRA32 font atlas.')
    line=struct.unpack_from('<I',abc,4)[0];scale=line/20
    icon_width=max(1,round(24*scale));icon_height=max(1,round(21*scale))
    cell_width=(icon_width+7)//4*4;cell_height=(icon_height+3)//4*4
    columns=width//cell_width
    if not columns or ((ICON_COUNT+columns-1)//columns)*cell_height>height:
        raise ValueError('Controller icons do not fit the extended font atlas.')
    canvas=bytearray(width*height*4);extra=[]
    for index in range(ICON_COUNT):
        family=FAMILIES[index//8];position=index%8
        x=(index%columns)*cell_width;y=(index//columns)*cell_height
        icon=Image.frombytes('RGBA',(24,21),icon_rgba(family,position))
        if (icon_width,icon_height)!=(24,21):
            icon=icon.resize((icon_width,icon_height),Image.Resampling.LANCZOS)
        pixels=icon.tobytes()
        for dy in range(icon_height):
            start=((y+dy)*width+x)*4
            canvas[start:start+icon_width*4]=pixels[dy*icon_width*4:(dy+1)*icon_width*4]
        extra.append(struct.pack('<4f4hI',x/width,(height+y)/(height*2),
                                 (x+icon_width)/width,(height+y+icon_height)/(height*2),
                                 -round(5*scale),round(23*scale),round(18*scale),-12851,0))
    original=[]
    for glyph in font.glyphs:
        u0,v0,u1,v1=struct.unpack_from('<4f',glyph)
        original.append(struct.pack('<4f',u0,v0/2,u1,v1/2)+glyph[16:])
    header=bytearray(abc[:24]);struct.pack_into('<I',header,12,height*2)
    struct.pack_into('<I',header,20,len(font.ranges)+1)
    ranges=b''.join(struct.pack('<HH',lo,hi) for lo,hi in font.ranges+[(BASE_CODE,BASE_CODE+ICON_COUNT-1)])
    newabc=bytes(header)+ranges+struct.pack('<I',len(original)+len(extra))+b''.join(original+extra)
    newdds=bytearray(dds[:128]);struct.pack_into('<I',newdds,12,height*2)
    if fmt==b'DXT5':appended=encode_dxt5(canvas,width,height)
    elif fmt==b'DXT3':appended=encode_dxt3(canvas,width,height)
    else:
        appended=bytearray(canvas);appended[0::4],appended[2::4]=canvas[2::4],canvas[0::4]
    if fmt!=b'BGRA':struct.pack_into('<I',newdds,20,width*height*2)
    return newabc,bytes(newdds)+dds[128:]+appended

"""Synthetic font fixtures, never original game assets. Own work: djultra64."""
import struct
import unittest

def font_fixture():
    # Version6, height20, texture256x512, ascent16, one range A..B.
    header=struct.pack('<6I',6,20,256,512,16,1)+struct.pack('<HHI',65,66,2)
    glyph=struct.pack('<4f4hI',0.0,0.125,0.0625,0.166015625,-2,15,12,0,0)
    abc=header+glyph*2
    dds=bytearray(128);dds[:4]=b'DDS ';struct.pack_into('<I',dds,4,124)
    struct.pack_into('<II',dds,12,512,256);struct.pack_into('<I',dds,20,131072)
    struct.pack_into('<I',dds,76,32);dds[84:88]=b'DXT5'
    return abc,bytes(dds)+bytes(range(256))*512

class GlyphAtlasTests(unittest.TestCase):
    def test_original_compressed_pixels_are_preserved_and_uv_pixel_sizes_match(self):
        from tools.glyph_atlas import extend_font,parse_font
        abc,dds=font_fixture();newabc,newdds=extend_font(abc,dds)
        self.assertEqual(newdds[128:128+len(dds)-128],dds[128:])
        self.assertEqual(struct.unpack_from('<II',newdds,12),(1024,256))
        before=parse_font(abc);after=parse_font(newabc)
        self.assertEqual(after.codes[:2],before.codes)
        for old,new in zip(before.glyphs,after.glyphs):
            olduv=struct.unpack_from('<4f',old);newuv=struct.unpack_from('<4f',new)
            self.assertEqual(new[16:],old[16:])
            self.assertEqual(newuv,(olduv[0],olduv[1]/2,olduv[2],olduv[3]/2))
        self.assertEqual(after.codes[-48:],list(range(0xe000,0xe030)))
        self.assertEqual(len(newdds),128+256*1024)

    def test_each_family_has_distinct_own_icon_regions(self):
        from tools.glyph_atlas import extend_font,parse_font
        abc,dds=font_fixture();newabc,newdds=extend_font(abc,dds);font=parse_font(newabc)
        entries=[struct.unpack_from('<4f',g) for g in font.glyphs[-48:]]
        self.assertEqual(len(set(entries)),48)
        self.assertTrue(any(newdds[128+131072:]))
        # Xbox A and Switch B at the same south position are different pictures.
        self.assertNotEqual(newdds[128+131072:128+131072+2048],newdds[128+131072+24576:128+131072+26624])

    def test_invalid_font_or_texture_fails_before_returning_modified_assets(self):
        from tools.glyph_atlas import extend_font
        abc,dds=font_fixture()
        for badabc,baddds in [(abc[:-1],dds),(abc,b'DDS bad'),(b'bad',dds),
                              (abc,dds[:84]+b'DXT1'+dds[88:]),(abc,dds[:-1])]:
            with self.subTest(size=len(badabc)),self.assertRaises(ValueError):extend_font(badabc,baddds)

    def test_selected_xelu_icons_preserve_color_and_nintendo_positions(self):
        from tools.glyph_atlas import icon_rgba
        import json
        from pathlib import Path
        mapping=json.loads(Path('assets/input/xelu/mapping.json').read_text())
        self.assertEqual(mapping['switch']['south'],'Switch_B.png')
        self.assertEqual(mapping['xbox360']['select'],'360_Back.png')
        a=icon_rgba('xbox360',0);b=icon_rgba('xbox360',1)
        def totals(data):return [sum(data[i] for i in range(c,len(data),4) if data[i-c+3]>127) for c in range(3)]
        ar,ag,ab=totals(a);br,bg,bb=totals(b)
        self.assertGreater(ag,ar)
        self.assertGreater(br,bg)

    def test_all_supported_atlas_sizes_and_formats_preserve_original_pixels_and_metrics(self):
        from tools.glyph_atlas import extend_font,parse_font
        from PIL import Image
        import io
        for width,height,fmt in [(512,512,b'DXT3'),(128,256,b'DXT3'),(128,256,b'BGRA')]:
            with self.subTest(width=width,fmt=fmt):
                abc,dds=font_fixture();abc=bytearray(abc);dds=bytearray(dds[:128])
                struct.pack_into('<II',abc,8,width,height)
                if width==128:struct.pack_into('<I',abc,4,16)
                struct.pack_into('<II',dds,12,height,width)
                if fmt==b'BGRA':
                    struct.pack_into('<7I',dds,76,32,65,0,32,0xff0000,0xff00,0xff)
                    struct.pack_into('<I',dds,104,0xff000000)
                    struct.pack_into('<I',dds,20,width*4);payload=bytes([19,37,53,255])*(width*height)
                else:
                    dds[84:88]=fmt;struct.pack_into('<I',dds,80,4);struct.pack_into('<I',dds,20,width*height)
                    payload=bytes(range(16))*(width*height//16)
                original=bytes(dds)+payload
                newabc,newdds=extend_font(bytes(abc),original)
                self.assertEqual(newdds[128:128+len(payload)],payload)
                before=parse_font(bytes(abc));after=parse_font(newabc)
                self.assertEqual((after.width,after.height),(width,height*2))
                self.assertEqual([g[16:] for g in after.glyphs[:2]],[g[16:] for g in before.glyphs])
                a=Image.open(io.BytesIO(original)).convert('RGBA')
                b=Image.open(io.BytesIO(newdds)).convert('RGBA')
                self.assertEqual(a.tobytes(),b.crop((0,0,width,height)).tobytes())
                # Atlas cells keep their aspect in pixel coordinates; no widescreen distortion.
                self.assertEqual(len(set(struct.unpack_from('<4f',g) for g in after.glyphs[-48:])),48)

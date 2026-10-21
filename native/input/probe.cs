// Own native ABI probe; no original game files. djultra64.
using System;
using System.IO;
using System.Runtime.InteropServices;
class NativeInputProbe {
 [DllImport("djultra-input.dll")] static extern int DjultraInitialize();
 [DllImport("djultra-input.dll")] static extern int DjultraGetPadCount();
 [DllImport("djultra-input.dll")] static extern int DjultraGetActiveFamily();
 [DllImport("djultra-input.dll")] static extern uint DjultraResolveGlyphForTest(uint code,int family);
 static int Main(string[] args) {
  using(var log=new StreamWriter(args[0])) {
   log.AutoFlush=true;
   int status=DjultraInitialize();log.WriteLine("INITIALIZE "+status);
   if((status&1)==0)return 1;
   if((status&2)!=0)return 2; // This is an own probe, not the game: no hook installed.
   log.WriteLine("PADS "+DjultraGetPadCount());log.WriteLine("ACTIVE "+DjultraGetActiveFamily());
   uint[] codes={0x2123,0x2124,0x2125,0x2126,0x2127,0x2128,0x212b,0x212c};
   for(int f=0;f<=6;f++)for(int a=0;a<8;a++) {
    uint result=DjultraResolveGlyphForTest(codes[a],f);
    uint expected=f==0?codes[a]:(uint)(0xe000+(f-1)*8+a);
    if(result!=expected){log.WriteLine("MISMATCH "+f+" "+a+" "+result);return 3;}
   }
   log.WriteLine("NATIVE_ABI_AND_ALL_56_GLYPH_CASES_PASS");
  }
  return 0;
 }
}

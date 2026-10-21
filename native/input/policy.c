/* Own work: djultra64. Paired against launcher/controllers.py by contract tests. */
#include "policy.h"
unsigned int dj_glyph_code(unsigned int original,int family,const unsigned char *positions) {
    static const unsigned short codes[8]={0x2123,0x2124,0x2125,0x2126,0x2127,0x2128,0x212b,0x212c};
    unsigned int i,position;
    if (family<1 || family>6) return original;
    for (i=0;i<8;i++) if (codes[i]==original) {
        position=positions?positions[i]:i;
        return position<8?0xe000+(family-1)*8+position:original;
    }
    return original;
}

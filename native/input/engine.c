/* Own work: djultra64. No device events or system-wide input are generated. */
#include "engine.h"
static void split(float *out,int slot,int value){
    /* Original stick processing uses separate digital direction slots. */
    if(value < -10922)out[slot]=1.0f;
    if(value > 10922)out[40+slot]=1.0f;
}
int dj_engine_state(void *state,unsigned int size,unsigned int buttons,
                    const short *axes,int connected){
    static const unsigned char slots[15]={0,1,2,3,6,10,7,8,9,4,5,11,12,13,14};
    unsigned char *bytes=state;float *out;unsigned int i;
    if(!state||size<360||!axes)return 0;
    bytes[4]=bytes[5]=0;
    for(i=0;i<16;i++)bytes[6+i]=0;
    out=(float*)(bytes+40);for(i=0;i<80;i++)out[i]=0;
    *(unsigned int*)(bytes+32)=connected?1:0;
    *(unsigned int*)(bytes+36)=connected?0:1;
    if(!connected)return 1;
    for(i=0;i<15;i++)bytes[6+slots[i]]=(buttons>>i)&1;
    split(out,0,axes[0]);split(out,1,axes[1]);
    /* The owned navigation profile consumes the left-stick direction slots.
       A deliberate stick wins; opposite D-pad directions cancel each other. */
    if(axes[0]>=-10922&&axes[0]<=10922){
        int horizontal=(int)((buttons>>14)&1)-(int)((buttons>>13)&1);
        split(out,0,horizontal*32767);
    }
    if(axes[1]>=-10922&&axes[1]<=10922){
        int vertical=(int)((buttons>>12)&1)-(int)((buttons>>11)&1);
        split(out,1,vertical*32767);
    }
    split(out,3,axes[2]);split(out,4,axes[3]);
    /* The game's existing trigger bindings use opposite halves of LZ.
       Preserve both actions even when the two triggers are held together. */
    if(axes[4]>10922)out[42]=1.0f;
    if(axes[5]>10922)out[2]=1.0f;
    return 1;
}

/* Own isolated PE32 test. Changes only this harness's SDL sample callbacks. */
#define CALL __attribute__((stdcall))
typedef unsigned int U32;
typedef unsigned char U8;
extern void *iat_DjultraInitialize,*iat_GetModuleHandleA,*iat_CreateFileA;
extern void *iat_WriteFile,*iat_CloseHandle,*iat_ExitProcess;
#define API(name,result,...) ((result(CALL*)(__VA_ARGS__))iat_##name)
static U8 state[1164];
static U32 sample_buttons;
static short sample_axes[6];
static U32 CALL clock_value(void){return 1234;}
static U8 button_value(void *handle,int index){(void)handle;return (sample_buttons>>index)&1;}
static short axis_value(void *handle,int index){(void)handle;return sample_axes[index];}
static void finish(int result){
    const char *message=result?"FAIL_ENGINE_ADAPTER\r\n":"ENGINE_CDECL_HOOK_15_BUTTONS_6_AXES_DISCONNECT_AND_FALLBACK_PASS\r\n";
    U32 length=0,written=0;void *file;
    while(message[length])length++;
    file=API(CreateFileA,void*,const char*,U32,U32,void*,U32,U32,void*)("native-engine-contract.txt",0x40000000,0,0,2,0x80,0);
    if(file!=(void*)-1){API(WriteFile,int,void*,const void*,U32,U32*,void*)(file,message,length,&written,0);API(CloseHandle,int,void*)(file);}
    API(ExitProcess,void,U32)((U32)result);for(;;){}
}
void _start(void){
    static const U8 positions[15]={0,1,2,3,6,10,7,8,9,4,5,11,12,13,14};
    U8 *module;U32 i,j,old,ignored;float *axes=(float*)(state+40);
    int (*read)(int,void*)=(void*)0x52d1e0;
    if(API(DjultraInitialize,int,void)()!=7)finish(10);
    module=API(GetModuleHandleA,void*,const char*)("djultra-input.dll");if(!module)finish(11);
    {
        int (CALL *protect)(void*,U32,U32,U32*)=*(void**)(module+DJ_PROTECT_RVA);
        if(!protect(module+DJ_CLOCK_RVA,4,4,&old))finish(12);
        *(void**)(module+DJ_CLOCK_RVA)=clock_value;
        if(!protect(module+DJ_CLOCK_RVA,4,old,&ignored))finish(13);
    }
    *(U32*)(module+DJ_LAST_POLL_RVA)=1234;*(U32*)(module+DJ_POLLED_RVA)=1;
    *(void**)(module+DJ_BUTTON_RVA)=button_value;*(void**)(module+DJ_AXIS_RVA)=axis_value;
    *(void**)(module+DJ_PADS_RVA+4)=(void*)1;
    for(i=0;i<15;i++){
        for(j=0;j<1164;j++)state[j]=0x5a;
        sample_buttons=1u<<i;if(read(1,state)!=0)finish(50);
        for(j=0;j<16;j++)if(state[6+j]!=(j==positions[i]))finish(20+i);
        if(*(U32*)state!=0x5a5a5a5a||state[1163]!=0x5a)finish(40);
    }
    sample_buttons=0;sample_axes[0]=-32768;sample_axes[1]=32767;
    sample_axes[2]=-16384;sample_axes[3]=16384;sample_axes[4]=32767;sample_axes[5]=16384;
    read(1,state);
    if(axes[0]!=1||axes[41]!=1||axes[3]!=1||axes[44]!=1||axes[42]!=1||axes[2]!=1)finish(41);
    *(void**)(module+DJ_PADS_RVA+4)=0;if(read(1,state)>=0)finish(52);
    for(i=0;i<80;i++)if(axes[i]!=0)finish(42);
    for(i=0;i<16;i++)if(state[6+i]!=0)finish(43);
    *(void**)(module+DJ_SDL_RVA)=0;if(read(1,state)!=37)finish(51);
    if(*(U32*)state!=0x12345678)finish(44);
    finish(0);
}

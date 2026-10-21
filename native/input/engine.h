/* Own work: djultra64. SDL physical positions -> existing engine state. */
#ifndef DJ_ENGINE_INPUT_H
#define DJ_ENGINE_INPUT_H
int dj_engine_state(void *state,unsigned int size,unsigned int buttons,
                    const short *axes,int connected);
#endif

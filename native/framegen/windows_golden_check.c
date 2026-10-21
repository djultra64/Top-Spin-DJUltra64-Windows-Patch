/* Reuse upstream GPU-output check for independent repeat-frame negative control.
 * Author: djultra64. SPDX-License-Identifier: MIT */
#include "headless.h"
uint32_t square_x(uint32_t frame) { return SQUARE_X0 + (frame * SQUARE_STEP) % SQUARE_WRAP; }
int main(int argc, char **argv) {
    if (argc != 2) return 2;
    return check_dump(argv[1], 8) ? 0 : 1;
}

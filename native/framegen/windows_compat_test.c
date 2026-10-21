/* Windows synchronization/monotonic contract checks. Author: djultra64. */
#include "windows_compat.h"
#ifdef NDEBUG
#undef NDEBUG
#endif
#include <assert.h>
#include <stdio.h>
static pthread_mutex_t lock = PTHREAD_MUTEX_INITIALIZER;
static pthread_cond_t condition;
static pthread_once_t once = PTHREAD_ONCE_INIT;
static int ready, initialized;
static LONG worker_timer_owners;
static void init_once(void) { ++initialized; }
static void *worker(void *argument) {
    worker_timer_owners = afmf_win_timer_test_state().owners;
    puts("worker starts");
    pthread_once(&once, init_once);
    puts("worker once finished");
    pthread_mutex_lock(&lock);
    ready = 1;
    pthread_cond_broadcast(&condition);
    pthread_mutex_unlock(&lock);
    return argument;
}
int main(void) {
    pthread_condattr_t attribute;
    pthread_t thread;
    struct timespec before, until, after;
    void *result = NULL;
    setbuf(stdout, NULL);
    puts("start");
    assert(afmf_win_timer_test_state().owners == 0);
    assert(afmf_win_timer_acquire() == 0);
    assert(afmf_win_timer_test_state().owners == 1);
    assert(afmf_win_timer_test_state().begin_calls == 1);
    pthread_condattr_init(&attribute);
    assert(pthread_condattr_setclock(&attribute, CLOCK_MONOTONIC) == 0);
    assert(pthread_cond_init(&condition, &attribute) == 0);
    assert(pthread_create(&thread, NULL, worker, (void *)42) == 0);
    puts("created thread");
    pthread_mutex_lock(&lock);
    while (!ready) assert(pthread_cond_wait(&condition, &lock) == 0);
    puts("worker signaled");
    const long durations[] = {10000000, 16666667, 20000000};
    for (unsigned i = 0; i < sizeof durations / sizeof durations[0]; ++i) {
        assert(clock_gettime(CLOCK_MONOTONIC, &before) == 0);
        until = before;
        until.tv_nsec += durations[i];
        if (until.tv_nsec >= 1000000000) { ++until.tv_sec; until.tv_nsec -= 1000000000; }
        assert(pthread_cond_timedwait(&condition, &lock, &until) == ETIMEDOUT);
        assert(clock_gettime(CLOCK_MONOTONIC, &after) == 0);
        assert(after.tv_sec > until.tv_sec || (after.tv_sec == until.tv_sec && after.tv_nsec >= until.tv_nsec));
        double elapsed_ms = (double)(after.tv_sec - before.tv_sec) * 1000.0 +
                            (double)(after.tv_nsec - before.tv_nsec) / 1000000.0;
        printf("Deadline requested %.3f ms, observed %.3f ms (Wine observation, no native precision claim)\n",
               durations[i] / 1000000.0, elapsed_ms);
    }
    pthread_mutex_unlock(&lock);
    assert(pthread_join(thread, &result) == 0 && result == (void *)42);
    pthread_once(&once, init_once);
    assert(initialized == 1);
    assert(worker_timer_owners >= 2);
    assert(afmf_win_timer_test_state().owners == 1);
    assert(afmf_win_timer_test_state().end_calls == 0);
    afmf_win_timer_release();
    assert(afmf_win_timer_test_state().owners == 0);
    assert(afmf_win_timer_test_state().begin_calls == 1);
    assert(afmf_win_timer_test_state().end_calls == 1);
    assert(afmf_win_timer_acquire() == 0);
    afmf_win_timer_release();
    assert(afmf_win_timer_test_state().begin_calls == 2);
    assert(afmf_win_timer_test_state().end_calls == 2);
    afmf_win_timer_test_fail_next_thread();
    assert(pthread_create(&thread, NULL, worker, NULL) == EAGAIN);
    assert(afmf_win_timer_test_state().owners == 0);
    assert(afmf_win_timer_test_state().begin_calls == 3);
    assert(afmf_win_timer_test_state().end_calls == 3);
    pthread_cond_destroy(&condition);
    pthread_condattr_destroy(&attribute);
    puts("PASS Windows synchronization, monotonic deadlines and balanced shared 1ms timer lifecycle");
    return 0;
}

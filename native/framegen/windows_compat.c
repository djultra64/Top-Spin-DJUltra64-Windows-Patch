/* AFMF Windows platform adapter. Integration copyright 2026 djultra64.
 * SPDX-License-Identifier: MIT
 */
#include "windows_compat.h"
#include <process.h>
#include <stdlib.h>
#include <mmsystem.h>

static SRWLOCK timer_lock = SRWLOCK_INIT;
static LONG timer_owners;
#ifdef AFMF_WINDOWS_COMPAT_TEST
static LONG timer_begin_calls, timer_end_calls;
static LONG fail_next_thread;
void afmf_win_timer_test_fail_next_thread(void)
{ InterlockedExchange(&fail_next_thread, 1); }
struct afmf_win_timer_state afmf_win_timer_test_state(void)
{
    AcquireSRWLockExclusive(&timer_lock);
    struct afmf_win_timer_state state = {timer_owners, timer_begin_calls, timer_end_calls};
    ReleaseSRWLockExclusive(&timer_lock);
    return state;
}
#endif

int afmf_win_timer_acquire(void)
{
    AcquireSRWLockExclusive(&timer_lock);
    if (timer_owners == LONG_MAX || (timer_owners == 0 && timeBeginPeriod(1) != TIMERR_NOERROR)) {
        ReleaseSRWLockExclusive(&timer_lock);
        return EAGAIN;
    }
#ifdef AFMF_WINDOWS_COMPAT_TEST
    if (timer_owners == 0) ++timer_begin_calls;
#endif
    ++timer_owners;
    ReleaseSRWLockExclusive(&timer_lock);
    return 0;
}

void afmf_win_timer_release(void)
{
    AcquireSRWLockExclusive(&timer_lock);
    if (timer_owners > 0 && --timer_owners == 0) {
        (void)timeEndPeriod(1);
#ifdef AFMF_WINDOWS_COMPAT_TEST
        ++timer_end_calls;
#endif
    }
    ReleaseSRWLockExclusive(&timer_lock);
}

struct afmf_win_thread {
    HANDLE handle;
    void *(*function)(void *);
    void *argument;
    void *result;
};

int afmf_win_clock_gettime(int clock, struct timespec *result)
{
    LARGE_INTEGER frequency, counter;
    if (clock != CLOCK_MONOTONIC || !result || !QueryPerformanceFrequency(&frequency) ||
        !QueryPerformanceCounter(&counter)) {
        errno = EINVAL;
        return -1;
    }
    result->tv_sec = (time_t)(counter.QuadPart / frequency.QuadPart);
    result->tv_nsec = (long)(((counter.QuadPart % frequency.QuadPart) * 1000000000LL) /
                              frequency.QuadPart);
    return 0;
}

int pthread_mutex_init(pthread_mutex_t *lock, const void *attribute)
{ (void)attribute; InitializeSRWLock(lock); return 0; }
int pthread_mutex_destroy(pthread_mutex_t *lock) { (void)lock; return 0; }
int pthread_mutex_lock(pthread_mutex_t *lock) { AcquireSRWLockExclusive(lock); return 0; }
int pthread_mutex_unlock(pthread_mutex_t *lock) { ReleaseSRWLockExclusive(lock); return 0; }
int pthread_rwlock_rdlock(pthread_rwlock_t *lock) { AcquireSRWLockExclusive(lock); return 0; }
int pthread_rwlock_wrlock(pthread_rwlock_t *lock) { AcquireSRWLockExclusive(lock); return 0; }
int pthread_rwlock_unlock(pthread_rwlock_t *lock) { ReleaseSRWLockExclusive(lock); return 0; }
int pthread_condattr_init(pthread_condattr_t *attribute) { *attribute = CLOCK_MONOTONIC; return 0; }
int pthread_condattr_setclock(pthread_condattr_t *attribute, int clock)
{ if (clock != CLOCK_MONOTONIC) return EINVAL; *attribute = clock; return 0; }
int pthread_condattr_destroy(pthread_condattr_t *attribute) { (void)attribute; return 0; }
int pthread_cond_init(pthread_cond_t *condition, const pthread_condattr_t *attribute)
{
    InitializeConditionVariable(&condition->native);
    condition->clock = attribute ? *attribute : CLOCK_MONOTONIC;
    return 0;
}
int pthread_cond_destroy(pthread_cond_t *condition) { (void)condition; return 0; }
int pthread_cond_wait(pthread_cond_t *condition, pthread_mutex_t *lock)
{
    return SleepConditionVariableSRW(&condition->native, lock, INFINITE, 0) ? 0 : EINVAL;
}
int pthread_cond_timedwait(pthread_cond_t *condition, pthread_mutex_t *lock,
                           const struct timespec *deadline)
{
    for (;;) {
        struct timespec now;
        if (afmf_win_clock_gettime(condition->clock, &now) != 0) return EINVAL;
        int64_t remaining = ((int64_t)deadline->tv_sec - (int64_t)now.tv_sec) * 1000000000LL +
                              deadline->tv_nsec - now.tv_nsec;
        if (remaining <= 0) return ETIMEDOUT;
        uint64_t milliseconds = ((uint64_t)remaining + 999999u) / 1000000u;
        DWORD timeout = milliseconds >= INFINITE ? INFINITE - 1 : (DWORD)milliseconds;
        if (SleepConditionVariableSRW(&condition->native, lock, timeout, 0)) return 0;
        if (GetLastError() != ERROR_TIMEOUT) return EINVAL;
        /* Recheck QPC: never convert a monotonic absolute deadline into wall time. */
    }
}
int pthread_cond_broadcast(pthread_cond_t *condition)
{ WakeAllConditionVariable(&condition->native); return 0; }
struct once_call { void (*function)(void); };
static BOOL CALLBACK call_once(PINIT_ONCE once, PVOID parameter, PVOID *context)
{
    (void)once; (void)context;
    ((struct once_call *)parameter)->function();
    return TRUE;
}
int pthread_once(pthread_once_t *once, void (*function)(void))
{
    struct once_call call = {function};
    return InitOnceExecuteOnce(once, call_once, &call, NULL) ? 0 : EINVAL;
}
static unsigned __stdcall thread_entry(void *parameter)
{
    struct afmf_win_thread *thread = parameter;
    thread->result = thread->function(thread->argument);
    afmf_win_timer_release();
    return 0;
}
int pthread_create(pthread_t *output, const void *attribute,
                   void *(*function)(void *), void *argument)
{
    (void)attribute;
    struct afmf_win_thread *thread = calloc(1, sizeof *thread);
    if (!thread) return ENOMEM;
    thread->function = function;
    thread->argument = argument;
    /* QPC measures time; it does not improve condition-variable wake granularity.
     * Acquire before starting the thread, release on its return or creation failure.
     * Never call Winmm from DllMain, nor register a second atexit cleanup. Regular
     * layer teardown joins all threads before unload; process termination releases
     * the process timer request without running unsafe loader-lock cleanup. */
    if (afmf_win_timer_acquire() != 0) { free(thread); return EAGAIN; }
#ifdef AFMF_WINDOWS_COMPAT_TEST
    if (InterlockedExchange(&fail_next_thread, 0)) thread->handle = NULL;
    else
#endif
        thread->handle = (HANDLE)_beginthreadex(NULL, 0, thread_entry, thread, 0, NULL);
    if (!thread->handle) { afmf_win_timer_release(); free(thread); return EAGAIN; }
    *output = thread;
    return 0;
}
int pthread_join(pthread_t thread, void **result)
{
    if (!thread || WaitForSingleObject(thread->handle, INFINITE) != WAIT_OBJECT_0) return EINVAL;
    if (result) *result = thread->result;
    CloseHandle(thread->handle);
    free(thread);
    return 0;
}

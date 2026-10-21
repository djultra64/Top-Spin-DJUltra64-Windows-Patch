/* AFMF Windows platform adapter. Integration copyright 2026 djultra64.
 * SPDX-License-Identifier: MIT
 * A deliberately bounded subset of pthreads, implemented with Windows APIs.
 */
#pragma once
#ifndef _WIN32
#error This adapter is only for Windows builds
#endif
#ifndef WIN32_LEAN_AND_MEAN
#define WIN32_LEAN_AND_MEAN
#endif
#include <windows.h>
#include <errno.h>
#include <stdint.h>
#include <time.h>

typedef SRWLOCK pthread_mutex_t;
/* Registry readers use an exclusive SRW lock too: safe symmetric unlock. */
typedef SRWLOCK pthread_rwlock_t;
typedef INIT_ONCE pthread_once_t;
typedef struct { CONDITION_VARIABLE native; int clock; } pthread_cond_t;
typedef int pthread_condattr_t;
struct afmf_win_thread;
typedef struct afmf_win_thread *pthread_t;
#define PTHREAD_MUTEX_INITIALIZER SRWLOCK_INIT
#define PTHREAD_RWLOCK_INITIALIZER SRWLOCK_INIT
#define PTHREAD_ONCE_INIT INIT_ONCE_STATIC_INIT
#ifndef CLOCK_MONOTONIC
#define CLOCK_MONOTONIC 1
#endif
#define clock_gettime afmf_win_clock_gettime
int afmf_win_clock_gettime(int clock, struct timespec *result);
/* Owned by live shim-created threads; balanced before each thread returns. */
int afmf_win_timer_acquire(void);
void afmf_win_timer_release(void);
#ifdef AFMF_WINDOWS_COMPAT_TEST
struct afmf_win_timer_state { LONG owners, begin_calls, end_calls; };
struct afmf_win_timer_state afmf_win_timer_test_state(void);
void afmf_win_timer_test_fail_next_thread(void);
#endif
int pthread_mutex_init(pthread_mutex_t *lock, const void *attribute);
int pthread_mutex_destroy(pthread_mutex_t *lock);
int pthread_mutex_lock(pthread_mutex_t *lock);
int pthread_mutex_unlock(pthread_mutex_t *lock);
int pthread_rwlock_rdlock(pthread_rwlock_t *lock);
int pthread_rwlock_wrlock(pthread_rwlock_t *lock);
int pthread_rwlock_unlock(pthread_rwlock_t *lock);
int pthread_condattr_init(pthread_condattr_t *attribute);
int pthread_condattr_setclock(pthread_condattr_t *attribute, int clock);
int pthread_condattr_destroy(pthread_condattr_t *attribute);
int pthread_cond_init(pthread_cond_t *condition, const pthread_condattr_t *attribute);
int pthread_cond_destroy(pthread_cond_t *condition);
int pthread_cond_wait(pthread_cond_t *condition, pthread_mutex_t *lock);
int pthread_cond_timedwait(pthread_cond_t *condition, pthread_mutex_t *lock,
                           const struct timespec *deadline);
int pthread_cond_broadcast(pthread_cond_t *condition);
int pthread_once(pthread_once_t *once, void (*function)(void));
int pthread_create(pthread_t *thread, const void *attribute, void *(*function)(void *), void *argument);
int pthread_join(pthread_t thread, void **result);

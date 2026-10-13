#include "selfcheck.h"

#include <freertos/semphr.h>
#include <freertos/task.h>
#include <pthread.h>
#include <signal.h>

static const int INTERRUPTING_SIGNAL = SIGUSR1;
static const size_t SIGNALS_PER_INTERRUPTED_WAIT = 50;
static const TickType_t TICKS_BETWEEN_INTERRUPTING_SIGNALS = 1;
static const TickType_t WAIT_TIMEOUT_TICKS = 300;

typedef struct {
    pthread_t waiting_thread;
    SemaphoreHandle_t semaphore_given_after_signals;
} wait_interrupter_t;

static volatile sig_atomic_t received_interrupting_signal_count = 0;

static void count_interrupting_signal(const int signal_number) { ++received_interrupting_signal_count; }

static void* interrupt_waiting_thread(void* wait_interrupter_context)
{
    const wait_interrupter_t* wait_interrupter = (const wait_interrupter_t*)wait_interrupter_context;
    for (size_t sent_signal_count = 0; sent_signal_count < SIGNALS_PER_INTERRUPTED_WAIT; ++sent_signal_count) {
        vTaskDelay(TICKS_BETWEEN_INTERRUPTING_SIGNALS);
        pthread_kill(wait_interrupter->waiting_thread, INTERRUPTING_SIGNAL);
    }
    if (wait_interrupter->semaphore_given_after_signals) {
        xSemaphoreGive(wait_interrupter->semaphore_given_after_signals);
    }
    return NULL;
}

static bool check_wait_with_timeout_retries_after_signals(void)
{
    SemaphoreHandle_t never_given_semaphore = xSemaphoreCreateBinary();
    if (!never_given_semaphore) {
        FAIL();
    }
    const wait_interrupter_t wait_interrupter
        = { .waiting_thread = pthread_self(), .semaphore_given_after_signals = NULL };
    pthread_t interrupter_thread;
    if (pthread_create(&interrupter_thread, NULL, interrupt_waiting_thread, (void*)&wait_interrupter)) {
        vSemaphoreDelete(never_given_semaphore);
        FAIL();
    }
    const TickType_t wait_start_ticks = xTaskGetTickCount();
    const int semaphore_was_taken = xSemaphoreTake(never_given_semaphore, WAIT_TIMEOUT_TICKS);
    const TickType_t waited_ticks = xTaskGetTickCount() - wait_start_ticks;
    pthread_join(interrupter_thread, NULL);
    vSemaphoreDelete(never_given_semaphore);
    if (semaphore_was_taken || waited_ticks < WAIT_TIMEOUT_TICKS) {
        FAIL();
    }
    return true;
}

static bool check_wait_without_timeout_retries_after_signals(void)
{
    SemaphoreHandle_t semaphore_given_after_signals = xSemaphoreCreateBinary();
    if (!semaphore_given_after_signals) {
        FAIL();
    }
    const wait_interrupter_t wait_interrupter
        = { .waiting_thread = pthread_self(), .semaphore_given_after_signals = semaphore_given_after_signals };
    pthread_t interrupter_thread;
    if (pthread_create(&interrupter_thread, NULL, interrupt_waiting_thread, (void*)&wait_interrupter)) {
        vSemaphoreDelete(semaphore_given_after_signals);
        FAIL();
    }
    const int semaphore_was_taken = xSemaphoreTake(semaphore_given_after_signals, portMAX_DELAY);
    pthread_join(interrupter_thread, NULL);
    const int semaphore_was_still_available = xSemaphoreTake(semaphore_given_after_signals, 0);
    vSemaphoreDelete(semaphore_given_after_signals);
    if (!semaphore_was_taken || semaphore_was_still_available) {
        FAIL();
    }
    return true;
}

bool debug_selfcheck(jade_process_t* process)
{
    struct sigaction interrupting_signal_action = { .sa_handler = count_interrupting_signal };
    struct sigaction previous_interrupting_signal_action;
    if (sigemptyset(&interrupting_signal_action.sa_mask)
        || sigaction(INTERRUPTING_SIGNAL, &interrupting_signal_action, &previous_interrupting_signal_action)) {
        FAIL();
    }
    const bool waits_retry_after_signals
        = check_wait_with_timeout_retries_after_signals() && check_wait_without_timeout_retries_after_signals();
    if (sigaction(INTERRUPTING_SIGNAL, &previous_interrupting_signal_action, NULL) || !waits_retry_after_signals
        || !received_interrupting_signal_count) {
        FAIL();
    }
    return true;
}

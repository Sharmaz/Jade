#ifndef UTILS_UNIFIED_SIGHASH_H_
#define UTILS_UNIFIED_SIGHASH_H_

#include "../jade_assert.h"

#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

struct wally_tx;

#define UNIFIED_SIGHASH_FLAG 0x20

typedef enum {
    UNIFIED_SIGHASH_SCRIPT_TYPE_BASE = 0,
    UNIFIED_SIGHASH_SCRIPT_TYPE_WITNESS_V0 = 1,
    UNIFIED_SIGHASH_SCRIPT_TYPE_TAPROOT = 2,
    UNIFIED_SIGHASH_SCRIPT_TYPE_TAPSCRIPT = 3
} unified_sighash_script_type_t;

typedef struct {
    uint64_t satoshi;
    const uint8_t* script;
    size_t script_len;
} unified_sighash_spent_output_t;

WARN_UNUSED_RESULT bool unified_sighash_get_digest(const struct wally_tx* tx, size_t input_index,
    const unified_sighash_spent_output_t* spent_outputs, size_t num_spent_outputs, const uint8_t* script_code,
    size_t script_code_len, uint8_t sighash, unified_sighash_script_type_t script_type, const uint8_t* tapleaf_hash,
    size_t tapleaf_hash_len, uint32_t codeseparator_position, uint8_t* output, size_t output_len);

#endif

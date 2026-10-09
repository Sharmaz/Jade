#ifndef AMALGAMATED_BUILD
#include "unified_sighash.h"
#include "jade_assert.h"
#include "jade_wally_verify.h"

#include <limits.h>
#include <mbedtls/sha256.h>
#include <string.h>
#include <wally_crypto.h>
#include <wally_script.h>
#include <wally_transaction.h>

static const char UNIFIED_SIGHASH_TAG[] = "UnifiedSighash";
static const uint8_t UNIFIED_SIGHASH_EPOCH = 0;
static const uint8_t UNIFIED_SIGHASH_LOCKTIME_EXTENSION = 0;
static const uint8_t UNIFIED_SIGHASH_NO_ANNEX = 0;
static const uint8_t UNIFIED_SIGHASH_TAPSCRIPT_KEY_VERSION = 0;

static void sha256_start(mbedtls_sha256_context* hash_context)
{
    JADE_ASSERT(hash_context);

    const int is_sha224 = 0;
    mbedtls_sha256_init(hash_context);
    JADE_ZERO_VERIFY(mbedtls_sha256_starts(hash_context, is_sha224));
}

static void sha256_update_bytes(mbedtls_sha256_context* hash_context, const uint8_t* bytes, const size_t bytes_len)
{
    JADE_ASSERT(hash_context);
    JADE_ASSERT(bytes || !bytes_len);

    if (bytes_len) {
        JADE_ZERO_VERIFY(mbedtls_sha256_update(hash_context, bytes, bytes_len));
    }
}

static void sha256_start_tagged(mbedtls_sha256_context* hash_context, const char* tag)
{
    JADE_ASSERT(tag);

    uint8_t tag_hash[SHA256_LEN];
    JADE_WALLY_VERIFY(wally_sha256((const unsigned char*)tag, strlen(tag), tag_hash, sizeof(tag_hash)));
    sha256_start(hash_context);
    sha256_update_bytes(hash_context, tag_hash, sizeof(tag_hash));
    sha256_update_bytes(hash_context, tag_hash, sizeof(tag_hash));
}

static void sha256_finish(mbedtls_sha256_context* hash_context, uint8_t* output, const size_t output_len)
{
    JADE_ASSERT(hash_context);
    JADE_ASSERT(output);
    JADE_ASSERT(output_len == SHA256_LEN);

    JADE_ZERO_VERIFY(mbedtls_sha256_finish(hash_context, output));
    mbedtls_sha256_free(hash_context);
}

static void sha256_update_uint8(mbedtls_sha256_context* hash_context, const uint8_t value)
{
    sha256_update_bytes(hash_context, &value, sizeof(value));
}

static void sha256_update_uint32_le(mbedtls_sha256_context* hash_context, const uint32_t value)
{
    uint8_t value_bytes[sizeof(value)];
    for (size_t byte_index = 0; byte_index < sizeof(value_bytes); ++byte_index) {
        value_bytes[byte_index] = (uint8_t)(value >> (CHAR_BIT * byte_index));
    }
    sha256_update_bytes(hash_context, value_bytes, sizeof(value_bytes));
}

static void sha256_update_uint64_le(mbedtls_sha256_context* hash_context, const uint64_t value)
{
    uint8_t value_bytes[sizeof(value)];
    for (size_t byte_index = 0; byte_index < sizeof(value_bytes); ++byte_index) {
        value_bytes[byte_index] = (uint8_t)(value >> (CHAR_BIT * byte_index));
    }
    sha256_update_bytes(hash_context, value_bytes, sizeof(value_bytes));
}

static void sha256_update_length_prefixed(
    mbedtls_sha256_context* hash_context, const uint8_t* bytes, const size_t bytes_len)
{
    uint8_t compact_size[WALLY_SCRIPT_VARINT_MAX_SIZE];
    size_t compact_size_len = 0;
    JADE_WALLY_VERIFY(wally_varint_to_bytes(bytes_len, compact_size, sizeof(compact_size), &compact_size_len));
    JADE_ASSERT(compact_size_len <= sizeof(compact_size));
    sha256_update_bytes(hash_context, compact_size, compact_size_len);
    sha256_update_bytes(hash_context, bytes, bytes_len);
}

static void sha256_update_prevout(mbedtls_sha256_context* hash_context, const struct wally_tx_input* input)
{
    JADE_ASSERT(input);

    sha256_update_bytes(hash_context, input->txhash, sizeof(input->txhash));
    sha256_update_uint32_le(hash_context, input->index);
}

static void sha256_update_output(
    mbedtls_sha256_context* hash_context, const uint64_t satoshi, const uint8_t* script, const size_t script_len)
{
    sha256_update_uint64_le(hash_context, satoshi);
    sha256_update_length_prefixed(hash_context, script, script_len);
}

static void get_prevouts_hash(const struct wally_tx* tx, uint8_t* output, const size_t output_len)
{
    mbedtls_sha256_context hash_context;
    sha256_start(&hash_context);
    for (size_t input_index = 0; input_index < tx->num_inputs; ++input_index) {
        sha256_update_prevout(&hash_context, &tx->inputs[input_index]);
    }
    sha256_finish(&hash_context, output, output_len);
}

static void get_spent_amounts_hash(const unified_sighash_spent_output_t* spent_outputs, const size_t num_spent_outputs,
    uint8_t* output, const size_t output_len)
{
    mbedtls_sha256_context hash_context;
    sha256_start(&hash_context);
    for (size_t spent_output_index = 0; spent_output_index < num_spent_outputs; ++spent_output_index) {
        sha256_update_uint64_le(&hash_context, spent_outputs[spent_output_index].satoshi);
    }
    sha256_finish(&hash_context, output, output_len);
}

static void get_spent_scripts_hash(const unified_sighash_spent_output_t* spent_outputs, const size_t num_spent_outputs,
    uint8_t* output, const size_t output_len)
{
    mbedtls_sha256_context hash_context;
    sha256_start(&hash_context);
    for (size_t spent_output_index = 0; spent_output_index < num_spent_outputs; ++spent_output_index) {
        const unified_sighash_spent_output_t* const spent_output = &spent_outputs[spent_output_index];
        sha256_update_length_prefixed(&hash_context, spent_output->script, spent_output->script_len);
    }
    sha256_finish(&hash_context, output, output_len);
}

static void get_sequences_hash(const struct wally_tx* tx, uint8_t* output, const size_t output_len)
{
    mbedtls_sha256_context hash_context;
    sha256_start(&hash_context);
    for (size_t input_index = 0; input_index < tx->num_inputs; ++input_index) {
        sha256_update_uint32_le(&hash_context, tx->inputs[input_index].sequence);
    }
    sha256_finish(&hash_context, output, output_len);
}

static void get_outputs_hash(const struct wally_tx* tx, uint8_t* output, const size_t output_len)
{
    mbedtls_sha256_context hash_context;
    sha256_start(&hash_context);
    for (size_t output_index = 0; output_index < tx->num_outputs; ++output_index) {
        const struct wally_tx_output* const tx_output = &tx->outputs[output_index];
        sha256_update_output(&hash_context, tx_output->satoshi, tx_output->script, tx_output->script_len);
    }
    sha256_finish(&hash_context, output, output_len);
}

static void get_single_output_hash(const struct wally_tx_output* tx_output, uint8_t* output, const size_t output_len)
{
    mbedtls_sha256_context hash_context;
    sha256_start(&hash_context);
    sha256_update_output(&hash_context, tx_output->satoshi, tx_output->script, tx_output->script_len);
    sha256_finish(&hash_context, output, output_len);
}

static bool is_valid_taproot_sighash(const uint8_t sighash)
{
    const uint8_t taproot_sighash_bits = WALLY_SIGHASH_MASK | WALLY_SIGHASH_ANYONECANPAY | UNIFIED_SIGHASH_FLAG;
    const uint8_t output_type = sighash & WALLY_SIGHASH_MASK;
    const bool has_only_taproot_sighash_bits = !(sighash & ~taproot_sighash_bits);
    const bool has_defined_output_type
        = output_type == WALLY_SIGHASH_ALL || output_type == WALLY_SIGHASH_NONE || output_type == WALLY_SIGHASH_SINGLE;
    return has_only_taproot_sighash_bits && has_defined_output_type;
}

bool unified_sighash_get_digest(const struct wally_tx* tx, const size_t input_index,
    const unified_sighash_spent_output_t* spent_outputs, const size_t num_spent_outputs, const uint8_t* script_code,
    const size_t script_code_len, const uint8_t sighash, const unified_sighash_script_type_t script_type,
    const uint8_t* tapleaf_hash, const size_t tapleaf_hash_len, const uint32_t codeseparator_position, uint8_t* output,
    const size_t output_len)
{
    JADE_ASSERT(tx);
    JADE_ASSERT(input_index < tx->num_inputs);
    JADE_ASSERT(spent_outputs);
    JADE_ASSERT(num_spent_outputs == tx->num_inputs);
    JADE_ASSERT(script_code || !script_code_len);
    JADE_ASSERT(script_type <= UNIFIED_SIGHASH_SCRIPT_TYPE_TAPSCRIPT);
    JADE_ASSERT(
        script_type != UNIFIED_SIGHASH_SCRIPT_TYPE_TAPSCRIPT || (tapleaf_hash && tapleaf_hash_len == SHA256_LEN));
    JADE_ASSERT(output);
    JADE_ASSERT(output_len == SHA256_LEN);

    const bool is_taproot
        = script_type == UNIFIED_SIGHASH_SCRIPT_TYPE_TAPROOT || script_type == UNIFIED_SIGHASH_SCRIPT_TYPE_TAPSCRIPT;
    const uint8_t output_type = sighash & WALLY_SIGHASH_MASK;
    const bool is_anyonecanpay = sighash & WALLY_SIGHASH_ANYONECANPAY;
    const bool signs_single_output = output_type == WALLY_SIGHASH_SINGLE;
    const bool signs_all_outputs = output_type != WALLY_SIGHASH_NONE && !signs_single_output;

    if (!(sighash & UNIFIED_SIGHASH_FLAG)) {
        return false;
    }
    if (is_taproot && !is_valid_taproot_sighash(sighash)) {
        return false;
    }
    if (signs_single_output && input_index >= tx->num_outputs) {
        return false;
    }

    uint8_t prevouts_hash[SHA256_LEN] = { 0 };
    uint8_t spent_amounts_hash[SHA256_LEN] = { 0 };
    uint8_t spent_scripts_hash[SHA256_LEN] = { 0 };
    uint8_t sequences_hash[SHA256_LEN] = { 0 };
    if (!is_anyonecanpay) {
        get_prevouts_hash(tx, prevouts_hash, sizeof(prevouts_hash));
        get_spent_amounts_hash(spent_outputs, num_spent_outputs, spent_amounts_hash, sizeof(spent_amounts_hash));
        get_spent_scripts_hash(spent_outputs, num_spent_outputs, spent_scripts_hash, sizeof(spent_scripts_hash));
        get_sequences_hash(tx, sequences_hash, sizeof(sequences_hash));
    }

    uint8_t outputs_hash[SHA256_LEN] = { 0 };
    if (signs_all_outputs) {
        get_outputs_hash(tx, outputs_hash, sizeof(outputs_hash));
    }

    uint8_t single_output_hash[SHA256_LEN] = { 0 };
    if (signs_single_output) {
        get_single_output_hash(&tx->outputs[input_index], single_output_hash, sizeof(single_output_hash));
    }

    mbedtls_sha256_context message_hash_context;
    sha256_start_tagged(&message_hash_context, UNIFIED_SIGHASH_TAG);
    sha256_update_uint8(&message_hash_context, UNIFIED_SIGHASH_EPOCH);
    sha256_update_uint8(&message_hash_context, sighash);
    sha256_update_uint32_le(&message_hash_context, tx->version);
    sha256_update_uint32_le(&message_hash_context, tx->locktime);
    sha256_update_uint8(&message_hash_context, UNIFIED_SIGHASH_LOCKTIME_EXTENSION);

    if (!is_anyonecanpay) {
        sha256_update_bytes(&message_hash_context, prevouts_hash, sizeof(prevouts_hash));
        sha256_update_bytes(&message_hash_context, spent_amounts_hash, sizeof(spent_amounts_hash));
        sha256_update_bytes(&message_hash_context, spent_scripts_hash, sizeof(spent_scripts_hash));
        sha256_update_bytes(&message_hash_context, sequences_hash, sizeof(sequences_hash));
    }
    if (signs_all_outputs) {
        sha256_update_bytes(&message_hash_context, outputs_hash, sizeof(outputs_hash));
    }

    sha256_update_uint8(&message_hash_context, (uint8_t)script_type);

    if (is_anyonecanpay) {
        const struct wally_tx_input* const input = &tx->inputs[input_index];
        const unified_sighash_spent_output_t* const spent_output = &spent_outputs[input_index];
        sha256_update_prevout(&message_hash_context, input);
        sha256_update_output(
            &message_hash_context, spent_output->satoshi, spent_output->script, spent_output->script_len);
        sha256_update_uint32_le(&message_hash_context, input->sequence);
    } else {
        sha256_update_uint32_le(&message_hash_context, (uint32_t)input_index);
    }

    if (is_taproot) {
        sha256_update_uint8(&message_hash_context, UNIFIED_SIGHASH_NO_ANNEX);
    } else {
        sha256_update_length_prefixed(&message_hash_context, script_code, script_code_len);
    }

    if (signs_single_output) {
        sha256_update_bytes(&message_hash_context, single_output_hash, sizeof(single_output_hash));
    }

    if (script_type == UNIFIED_SIGHASH_SCRIPT_TYPE_TAPSCRIPT) {
        sha256_update_bytes(&message_hash_context, tapleaf_hash, tapleaf_hash_len);
        sha256_update_uint8(&message_hash_context, UNIFIED_SIGHASH_TAPSCRIPT_KEY_VERSION);
        sha256_update_uint32_le(&message_hash_context, codeseparator_position);
    }

    sha256_finish(&message_hash_context, output, output_len);
    return true;
}
#endif

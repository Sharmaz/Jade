#ifndef AMALGAMATED_BUILD
#include "../jade_assert.h"
#include "../process.h"
#include "../utils/cbor_rpc.h"
#include "../utils/malloc_ext.h"
#include "../utils/unified_sighash.h"
#include "../utils/wally_ext.h"

#include <cbor.h>
#include <wally_crypto.h>
#include <wally_transaction.h>

#include "process_utils.h"

#ifdef CONFIG_DEBUG_MODE

static bool get_byte_string_field(const CborValue* map, const char* field, const uint8_t** data, size_t* data_len)
{
    JADE_ASSERT(map);
    JADE_ASSERT(field);
    JADE_INIT_OUT_PPTR(data);
    JADE_INIT_OUT_SIZE(data_len);

    CborValue field_value;
    if (cbor_value_map_find_value(map, field, &field_value) != CborNoError || !cbor_value_is_byte_string(&field_value)
        || !cbor_value_is_length_known(&field_value)) {
        return false;
    }
    rpc_get_raw_bytes_ptr(&field_value, data, data_len);
    return true;
}

static bool get_spent_outputs(
    const CborValue* spent_outputs_array, unified_sighash_spent_output_t* spent_outputs, const size_t num_spent_outputs)
{
    JADE_ASSERT(spent_outputs_array);
    JADE_ASSERT(spent_outputs);

    CborValue spent_output_value;
    if (cbor_value_enter_container(spent_outputs_array, &spent_output_value) != CborNoError) {
        return false;
    }
    for (size_t spent_output_index = 0; spent_output_index < num_spent_outputs; ++spent_output_index) {
        unified_sighash_spent_output_t* const spent_output = &spent_outputs[spent_output_index];
        if (!cbor_value_is_map(&spent_output_value)
            || !rpc_get_uint64("satoshi", &spent_output_value, &spent_output->satoshi)
            || !get_byte_string_field(&spent_output_value, "script", &spent_output->script, &spent_output->script_len)
            || cbor_value_advance(&spent_output_value) != CborNoError) {
            return false;
        }
    }
    return true;
}

void debug_unified_sighash_process(void* process_ptr)
{
    JADE_LOGI("Starting: %d", xPortGetFreeHeapSize());
    jade_process_t* process = process_ptr;

    ASSERT_CURRENT_MESSAGE(process, "debug_unified_sighash");
    GET_MSG_PARAMS(process);

    const uint8_t* tx_bytes = NULL;
    size_t tx_bytes_len = 0;
    rpc_get_bytes_ptr("txn", &params, &tx_bytes, &tx_bytes_len);
    struct wally_tx* tx = NULL;
    if (!tx_bytes_len || wally_tx_from_bytes(tx_bytes, tx_bytes_len, 0, &tx) != WALLY_OK || !tx) {
        jade_process_reject_message(process, CBOR_RPC_BAD_PARAMETERS, "Failed to extract tx from parameters");
        goto cleanup;
    }
    jade_process_call_on_exit(process, jade_wally_free_tx_wrapper, tx);

    uint32_t input_index = 0;
    if (!rpc_get_uint32("input_index", &params, &input_index) || input_index >= tx->num_inputs) {
        jade_process_reject_message(
            process, CBOR_RPC_BAD_PARAMETERS, "Failed to extract valid input index from parameters");
        goto cleanup;
    }

    CborValue spent_outputs_array;
    size_t num_spent_outputs = 0;
    if (!rpc_get_array("spent_outputs", &params, &spent_outputs_array, &num_spent_outputs)
        || num_spent_outputs != tx->num_inputs) {
        jade_process_reject_message(
            process, CBOR_RPC_BAD_PARAMETERS, "Expecting one spent output per transaction input");
        goto cleanup;
    }
    unified_sighash_spent_output_t* const spent_outputs
        = JADE_CALLOC(num_spent_outputs, sizeof(unified_sighash_spent_output_t));
    jade_process_free_on_exit(process, spent_outputs);
    if (!get_spent_outputs(&spent_outputs_array, spent_outputs, num_spent_outputs)) {
        jade_process_reject_message(
            process, CBOR_RPC_BAD_PARAMETERS, "Failed to extract spent outputs from parameters");
        goto cleanup;
    }

    const uint8_t* script_code = NULL;
    size_t script_code_len = 0;
    if (!get_byte_string_field(&params, "script_code", &script_code, &script_code_len)) {
        jade_process_reject_message(process, CBOR_RPC_BAD_PARAMETERS, "Failed to extract script code from parameters");
        goto cleanup;
    }

    uint32_t sighash = 0;
    if (!rpc_get_uint32("sighash", &params, &sighash) || sighash > UINT8_MAX) {
        jade_process_reject_message(
            process, CBOR_RPC_BAD_PARAMETERS, "Failed to extract valid sighash from parameters");
        goto cleanup;
    }

    uint32_t script_type = 0;
    if (!rpc_get_uint32("script_type", &params, &script_type) || script_type > UNIFIED_SIGHASH_SCRIPT_TYPE_TAPSCRIPT) {
        jade_process_reject_message(
            process, CBOR_RPC_BAD_PARAMETERS, "Failed to extract valid script type from parameters");
        goto cleanup;
    }

    const bool is_tapscript = script_type == UNIFIED_SIGHASH_SCRIPT_TYPE_TAPSCRIPT;
    uint8_t tapleaf_hash[SHA256_LEN] = { 0 };
    uint32_t codeseparator_position = WALLY_NO_CODESEPARATOR;
    if (is_tapscript
        && (!rpc_get_n_bytes("tapleaf_hash", &params, sizeof(tapleaf_hash), tapleaf_hash)
            || !rpc_get_uint32("codeseparator_position", &params, &codeseparator_position))) {
        jade_process_reject_message(process, CBOR_RPC_BAD_PARAMETERS,
            "Failed to extract tapleaf hash and codeseparator position from parameters");
        goto cleanup;
    }

    uint8_t digest[SHA256_LEN];
    if (!unified_sighash_get_digest(tx, input_index, spent_outputs, num_spent_outputs, script_code, script_code_len,
            (uint8_t)sighash, (unified_sighash_script_type_t)script_type, is_tapscript ? tapleaf_hash : NULL,
            is_tapscript ? sizeof(tapleaf_hash) : 0, codeseparator_position, digest, sizeof(digest))) {
        jade_process_reject_message(process, CBOR_RPC_BAD_PARAMETERS, "Failed to compute unified sighash");
        goto cleanup;
    }

    jade_process_reply_to_message_bytes(&process->ctx, digest, sizeof(digest));
    JADE_LOGI("Success");

cleanup:
    return;
}
#endif
#endif

#include "main/utils/cbor_rpc.h"
#include "selfcheck.h"

#include <string.h>

#define VERSION_INFORMATION_REPLY_MAX_LENGTH 1024
#define TEMPORARY_WALLET_FIELD_NAME "NEFRITA_HAS_TEMPORARY_WALLET"

void build_version_info_reply(const void* message_source, CborEncoder* reply_encoder);

static bool load_wallet_and_check_version_information(const keychain_t* test_keychain,
    const jade_msg_source_t associated_source, const bool is_temporary, const jade_msg_source_t connection_source,
    const char* expected_state)
{
    keychain_set(test_keychain, associated_source, is_temporary);

    uint8_t version_information_reply[VERSION_INFORMATION_REPLY_MAX_LENGTH];
    CborEncoder reply_encoder;
    cbor_encoder_init(&reply_encoder, version_information_reply, sizeof(version_information_reply), 0);
    build_version_info_reply(&connection_source, &reply_encoder);
    const size_t reply_length = cbor_encoder_get_buffer_size(&reply_encoder, version_information_reply);

    CborParser reply_parser;
    CborValue version_information;
    if (cbor_parser_init(version_information_reply, reply_length, 0, &reply_parser, &version_information)
        != CborNoError) {
        FAIL();
    }

    const char* reported_state = NULL;
    size_t reported_state_length = 0;
    rpc_get_string_ptr("JADE_STATE", &version_information, &reported_state, &reported_state_length);
    if (reported_state_length != strlen(expected_state)
        || strncmp(reported_state, expected_state, reported_state_length) != 0) {
        FAIL();
    }

#ifdef CONFIG_XBT
    bool reported_has_temporary_wallet = false;
    if (!rpc_get_bool(TEMPORARY_WALLET_FIELD_NAME, &version_information, &reported_has_temporary_wallet)
        || reported_has_temporary_wallet != is_temporary) {
        FAIL();
    }
#else
    if (rpc_has_field_data(TEMPORARY_WALLET_FIELD_NAME, &version_information)) {
        FAIL();
    }
#endif
    return true;
}

bool debug_selfcheck(jade_process_t* process)
{
    JADE_ASSERT(process);
    const jade_msg_source_t connection_source = process->ctx.source;

    keychain_t test_keychain = { 0 };
    if (!keychain_derive_from_mnemonic(TEST_MNEMONIC, NULL, &test_keychain)) {
        FAIL();
    }

    if (!load_wallet_and_check_version_information(&test_keychain, SOURCE_NONE, true, connection_source, "TEMP")) {
        FAIL();
    }
    if (!load_wallet_and_check_version_information(
            &test_keychain, connection_source, true, connection_source, "READY")) {
        FAIL();
    }
    if (!load_wallet_and_check_version_information(
            &test_keychain, SOURCE_INTERNAL, true, connection_source, "LOCKED")) {
        FAIL();
    }
    if (!load_wallet_and_check_version_information(&test_keychain, SOURCE_NONE, false, connection_source, "UNSAVED")) {
        FAIL();
    }
    if (!load_wallet_and_check_version_information(
            &test_keychain, connection_source, false, connection_source, "READY")) {
        FAIL();
    }
    if (!load_wallet_and_check_version_information(
            &test_keychain, SOURCE_INTERNAL, false, connection_source, "LOCKED")) {
        FAIL();
    }

    keychain_clear();
    return true;
}

#include "main/utils/unified_signature.h"
#include "main/utils/unified_sighash.h"
#include "selfcheck.h"

#include <string.h>
#include <wally_crypto.h>

static const char SELFCHECK_PRIVATE_KEY_LABEL[] = "unified signature selfcheck private key";
static const char SELFCHECK_SIGNED_DIGEST_LABEL[] = "unified signature selfcheck signed digest";
static const char SELFCHECK_UNRELATED_DIGEST_LABEL[] = "unified signature selfcheck unrelated digest";
static const uint8_t SELFCHECK_EVEN_Y_PUBLIC_KEY_PREFIX = 0x02;

static bool sha256_of_label(const char* label, uint8_t* label_hash, const size_t label_hash_length)
{
    return wally_sha256((const unsigned char*)label, strlen(label), label_hash, label_hash_length) == WALLY_OK;
}

static bool check_ecdsa_verification(
    const uint8_t* private_key, const uint8_t* signed_digest, const uint8_t* unrelated_digest)
{
    uint8_t public_key[EC_PUBLIC_KEY_LEN];
    uint8_t compact_signature[EC_SIGNATURE_LEN];
    uint8_t signature[EC_SIGNATURE_DER_MAX_LEN + 1];
    size_t der_signature_length = 0;
    if (wally_ec_public_key_from_private_key(private_key, EC_PRIVATE_KEY_LEN, public_key, sizeof(public_key))
            != WALLY_OK
        || wally_ec_sig_from_bytes(private_key, EC_PRIVATE_KEY_LEN, signed_digest, SHA256_LEN,
               EC_FLAG_ECDSA | EC_FLAG_GRIND_R, compact_signature, sizeof(compact_signature))
            != WALLY_OK
        || wally_ec_sig_to_der(
               compact_signature, sizeof(compact_signature), signature, EC_SIGNATURE_DER_MAX_LEN, &der_signature_length)
            != WALLY_OK
        || der_signature_length > EC_SIGNATURE_DER_MAX_LEN) {
        FAIL();
    }
    const size_t signature_length = der_signature_length + 1;

    signature[der_signature_length] = UNIFIED_SIGHASH_ALL;
    if (!unified_signature_verify_ecdsa(
            public_key, sizeof(public_key), signed_digest, SHA256_LEN, signature, signature_length)) {
        FAIL();
    }
    if (unified_signature_verify_ecdsa(
            public_key, sizeof(public_key), unrelated_digest, SHA256_LEN, signature, signature_length)) {
        FAIL();
    }
    if (unified_signature_verify_ecdsa(
            public_key, sizeof(public_key), signed_digest, SHA256_LEN, signature, der_signature_length)) {
        FAIL();
    }

    signature[der_signature_length] = WALLY_SIGHASH_ALL;
    if (unified_signature_verify_ecdsa(
            public_key, sizeof(public_key), signed_digest, SHA256_LEN, signature, signature_length)) {
        FAIL();
    }
    return true;
}

static bool check_schnorr_verification(
    const uint8_t* private_key, const uint8_t* signed_digest, const uint8_t* unrelated_digest)
{
    uint8_t public_key[EC_PUBLIC_KEY_LEN];
    uint8_t tweaked_private_key[EC_PRIVATE_KEY_LEN];
    uint8_t tweaked_public_key[EC_PUBLIC_KEY_LEN];
    uint8_t signature[EC_SIGNATURE_LEN + 1];
    if (wally_ec_public_key_from_private_key(private_key, EC_PRIVATE_KEY_LEN, public_key, sizeof(public_key))
            != WALLY_OK
        || wally_ec_private_key_bip341_tweak(
               private_key, EC_PRIVATE_KEY_LEN, NULL, 0, 0, tweaked_private_key, sizeof(tweaked_private_key))
            != WALLY_OK
        || wally_ec_public_key_bip341_tweak(
               public_key, sizeof(public_key), NULL, 0, 0, tweaked_public_key, sizeof(tweaked_public_key))
            != WALLY_OK
        || wally_ec_sig_from_bytes(tweaked_private_key, sizeof(tweaked_private_key), signed_digest, SHA256_LEN,
               EC_FLAG_SCHNORR, signature, EC_SIGNATURE_LEN)
            != WALLY_OK) {
        FAIL();
    }

    uint8_t output_key[EC_PUBLIC_KEY_LEN];
    output_key[0] = SELFCHECK_EVEN_Y_PUBLIC_KEY_PREFIX;
    memcpy(output_key + 1, tweaked_public_key + 1, EC_XONLY_PUBLIC_KEY_LEN);

    signature[EC_SIGNATURE_LEN] = UNIFIED_SIGHASH_ALL;
    if (!unified_signature_verify_schnorr(
            output_key, sizeof(output_key), signed_digest, SHA256_LEN, signature, sizeof(signature))) {
        FAIL();
    }
    if (unified_signature_verify_schnorr(
            output_key, sizeof(output_key), unrelated_digest, SHA256_LEN, signature, sizeof(signature))) {
        FAIL();
    }
    if (unified_signature_verify_schnorr(
            output_key, sizeof(output_key), signed_digest, SHA256_LEN, signature, EC_SIGNATURE_LEN)) {
        FAIL();
    }

    signature[EC_SIGNATURE_LEN] = WALLY_SIGHASH_ALL;
    if (unified_signature_verify_schnorr(
            output_key, sizeof(output_key), signed_digest, SHA256_LEN, signature, sizeof(signature))) {
        FAIL();
    }
    return true;
}

bool debug_selfcheck(jade_process_t* process)
{
    uint8_t private_key[EC_PRIVATE_KEY_LEN];
    uint8_t signed_digest[SHA256_LEN];
    uint8_t unrelated_digest[SHA256_LEN];
    if (!sha256_of_label(SELFCHECK_PRIVATE_KEY_LABEL, private_key, sizeof(private_key))
        || wally_ec_private_key_verify(private_key, sizeof(private_key)) != WALLY_OK
        || !sha256_of_label(SELFCHECK_SIGNED_DIGEST_LABEL, signed_digest, sizeof(signed_digest))
        || !sha256_of_label(SELFCHECK_UNRELATED_DIGEST_LABEL, unrelated_digest, sizeof(unrelated_digest))) {
        FAIL();
    }
    if (!check_ecdsa_verification(private_key, signed_digest, unrelated_digest)) {
        FAIL();
    }
    if (!check_schnorr_verification(private_key, signed_digest, unrelated_digest)) {
        FAIL();
    }
    return true;
}

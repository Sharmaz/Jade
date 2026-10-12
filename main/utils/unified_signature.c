#ifndef AMALGAMATED_BUILD
#include "unified_signature.h"
#include "jade_assert.h"
#include "unified_sighash.h"

#include <wally_crypto.h>

static bool ends_with_unified_sighash_all(const uint8_t* signature, const size_t signature_length)
{
    return signature_length && signature[signature_length - 1] == UNIFIED_SIGHASH_ALL;
}

bool unified_signature_verify_ecdsa(const uint8_t* public_key, const size_t public_key_length, const uint8_t* digest,
    const size_t digest_length, const uint8_t* signature, const size_t signature_length)
{
    JADE_ASSERT(public_key);
    JADE_ASSERT(public_key_length == EC_PUBLIC_KEY_LEN);
    JADE_ASSERT(digest);
    JADE_ASSERT(digest_length == SHA256_LEN);
    JADE_ASSERT(signature || !signature_length);

    if (!ends_with_unified_sighash_all(signature, signature_length)) {
        return false;
    }

    const size_t der_signature_length = signature_length - 1;
    uint8_t compact_signature[EC_SIGNATURE_LEN];
    return wally_ec_sig_from_der(signature, der_signature_length, compact_signature, sizeof(compact_signature))
        == WALLY_OK
        && wally_ec_sig_verify(public_key, public_key_length, digest, digest_length, EC_FLAG_ECDSA, compact_signature,
               sizeof(compact_signature))
        == WALLY_OK;
}

bool unified_signature_verify_schnorr(const uint8_t* public_key, const size_t public_key_length, const uint8_t* digest,
    const size_t digest_length, const uint8_t* signature, const size_t signature_length)
{
    JADE_ASSERT(public_key);
    JADE_ASSERT(public_key_length == EC_PUBLIC_KEY_LEN);
    JADE_ASSERT(digest);
    JADE_ASSERT(digest_length == SHA256_LEN);
    JADE_ASSERT(signature || !signature_length);

    if (signature_length != EC_SIGNATURE_LEN + 1 || !ends_with_unified_sighash_all(signature, signature_length)) {
        return false;
    }
    return wally_ec_sig_verify(
               public_key, public_key_length, digest, digest_length, EC_FLAG_SCHNORR, signature, EC_SIGNATURE_LEN)
        == WALLY_OK;
}
#endif

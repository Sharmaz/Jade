#ifndef UTILS_UNIFIED_SIGNATURE_H_
#define UTILS_UNIFIED_SIGNATURE_H_

#include "../jade_assert.h"

#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

WARN_UNUSED_RESULT bool unified_signature_verify_ecdsa(const uint8_t* public_key, size_t public_key_length,
    const uint8_t* digest, size_t digest_length, const uint8_t* signature, size_t signature_length);

WARN_UNUSED_RESULT bool unified_signature_verify_schnorr(const uint8_t* public_key, size_t public_key_length,
    const uint8_t* digest, size_t digest_length, const uint8_t* signature, size_t signature_length);

#endif

#ifndef XBT_SIGHASH_BAN_H_
#define XBT_SIGHASH_BAN_H_

#include "sdkconfig.h"

#ifdef CONFIG_XBT
#include <wally_psbt.h>
#include <wally_transaction.h>

#pragma GCC poison wally_tx_get_btc_signature_hash
#pragma GCC poison wally_tx_get_btc_taproot_signature_hash
#pragma GCC poison wally_tx_get_signature_hash
#pragma GCC poison wally_tx_get_input_signature_hash
#pragma GCC poison wally_tx_get_elements_signature_hash
#pragma GCC poison wally_psbt_get_input_signature_hash
#pragma GCC poison wally_psbt_sign
#pragma GCC poison wally_psbt_sign_bip32
#endif

#endif

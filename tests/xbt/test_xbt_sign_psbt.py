from collections import namedtuple

from . import *
from ..rpc.unified_sighash_reference import (
    SCRIPT_TYPE_BASE, SCRIPT_TYPE_TAPROOT, SCRIPT_TYPE_WITNESS_V0, SIGHASH_ALL,
    SIGHASH_ANYONECANPAY, SIGHASH_NONE, SIGHASH_SINGLE, SIGHASH_UNIFIED, UINT32_LEN, TxOutput,
    parse_transaction_without_witness, sha256, unified_sighash)

pytestmark = xbt_firmware_only

UNIFIED_SIGHASH_ALL = SIGHASH_ALL | SIGHASH_UNIFIED
ABSENT_SIGHASH = 0
SIGHASH_FORKID = 0x40
SUPPORTED_DECLARED_SIGHASHES = [ABSENT_SIGHASH, SIGHASH_ALL, UNIFIED_SIGHASH_ALL]
UNSUPPORTED_DECLARED_SIGHASHES = [
    SIGHASH_NONE,
    SIGHASH_SINGLE,
    SIGHASH_ALL | SIGHASH_ANYONECANPAY,
    SIGHASH_NONE | SIGHASH_UNIFIED,
    UNIFIED_SIGHASH_ALL | SIGHASH_ANYONECANPAY,
    UNIFIED_SIGHASH_ALL | SIGHASH_FORKID,
]

UNSUPPORTED_SIGHASH_ERROR_MESSAGE = 'Unsupported sighash value'
NON_UNIFIED_SIGNATURE_ERROR_MESSAGE = 'Input has a signature without the unified sighash'
UNIFIED_SIGNATURE_VERIFICATION_ERROR_MESSAGE = 'Failed to verify the unified signature'
MISSING_UTXO_ERROR_MESSAGE = 'Input utxo missing'
NON_SINGLESIG_INPUT_ERROR_MESSAGE = 'Only singlesig inputs are supported'
UNSUPPORTED_SIGHASH_REQUEST_ID = 'bad_sighash'
NON_UNIFIED_SIGNATURE_REQUEST_ID = 'prior_signature'
SIGNATURE_OVER_ANOTHER_DIGEST_REQUEST_ID = 'other_digest'
MISSING_UTXO_REQUEST_ID = 'missing_utxo'
NON_SINGLESIG_INPUT_REQUEST_ID = 'non_singlesig'

FIXTURE_DIRECTORY = 'tests/rpc/data/sign_psbt'
BASE64_PREFIX = 'b64:'
DECLARED_SIGHASH_FIXTURE = 'psbt_ss_p2wpkh'
SIGNATURE_OVER_ANOTHER_DIGEST_FIXTURE = 'psbt_ss_p2wpkh'
SIGNATURE_OVER_ANOTHER_DIGEST_INPUT_INDEX = 0
ANOTHER_TRANSACTION_DIGEST = sha256(b'another transaction')
MISSING_UTXO_FIXTURE = 'psbt_ss_p2wpkh'
MISSING_UTXO_INPUT_INDEX = 1
OTHER_WALLET_MULTISIG_FIXTURE = 'psbt_ss_p2wsh_multisig'
OTHER_WALLET_MULTISIG_INPUT_INDEX = 0
BITCOIN_TAPROOT_SIGNATURE_FIXTURE = 'psbt_ss_p2tr_default_all'
BITCOIN_TAPROOT_SIGNATURE_INPUT_INDEX_PARAMETERS = [
    pytest.param(0, id='default_sighash'),
    pytest.param(1, id='sighash_all'),
]
SIGNED_TWICE_FIXTURES = ['psbt_ss_p2wpkh', 'psbt_ss_p2tr_default_all']
SINGLESIG_MNEMONIC_FIXTURES = [
    'psbt_ss_not_us',
    'psbt_ss_p2pkh',
    'psbt_ss_p2pkh_v2',
    'psbt_ss_p2sh_p2wpkh',
    'psbt_ss_p2tr_default_all',
    'psbt_ss_p2wpkh',
    'psbt_ss_p2wpkh_spend_coinbase',
]
DEFAULT_MNEMONIC_FIXTURES = [
    'psbt_tm_multisig_segwit_many_inputs',
    'psbt_tm_p2sh_segwit',
    'psbt_tm_segwit',
]
SINGLESIG_MNEMONIC_FIXTURES_WITH_NON_UNIFIED_SIGNATURE = ['psbt_ss_p2wpkh_already_signed']
SINGLESIG_MNEMONIC_FIXTURES_WITH_MULTISIG_INPUT = [
    'psbt_ss_p2sh_multisig',
    'psbt_ss_p2sh_p2wsh_multisig',
    'psbt_ss_p2wsh_multisig',
]
DEFAULT_MNEMONIC_FIXTURES_WITH_MULTISIG_INPUT = [
    'psbt_tm_green_multisig_2of2csv',
    'psbt_tm_green_multisig_2of3',
    'psbt_tm_green_multisig_2of3_recovery_signing',
    'psbt_tm_green_multisig_2of3_recovery_signing_full_path',
    'psbt_tm_multisig_p2sh_segwit',
    'psbt_tm_multisig_partial_p2sh_segwit',
    'psbt_tm_multisig_partial_segwit',
    'psbt_tm_multisig_segwit',
    'psbt_tm_multisig_segwit_many_inputs_2',
]

SCRIPT_TYPE_BY_SIGNATURE_TYPE = {
    wally.WALLY_SIGTYPE_PRE_SW: SCRIPT_TYPE_BASE,
    wally.WALLY_SIGTYPE_SW_V0: SCRIPT_TYPE_WITNESS_V0,
    wally.WALLY_SIGTYPE_SW_V1: SCRIPT_TYPE_TAPROOT,
}
FINGERPRINT_LENGTH = 4
EVEN_Y_PUBLIC_KEY_PREFIX = b'\x02'
P2TR_SCRIPTPUBKEY_OUTPUT_KEY_OFFSET = 2

PsbtFixture = namedtuple('PsbtFixture', ['network', 'psbt_bytes', 'bitcoin_signed_psbt_bytes'])


def _decode_psbt(encoded_psbt):
    assert encoded_psbt.startswith(BASE64_PREFIX)
    return base64.b64decode(encoded_psbt[len(BASE64_PREFIX):])


def _load_fixture(fixture_name):
    with open(f'{FIXTURE_DIRECTORY}/{fixture_name}.json', 'r') as fixture_file:
        fixture_json = json.load(fixture_file)
    return PsbtFixture(XBT_NETWORK_BY_BITCOIN_NETWORK[fixture_json['input']['network']],
                       _decode_psbt(fixture_json['input']['psbt']),
                       _decode_psbt(fixture_json['expected_output']['psbt']))


def _fixture_parameters(fixture_names):
    return [pytest.param(_load_fixture(fixture_name), id=fixture_name)
            for fixture_name in fixture_names]


def _input_indexes(psbt):
    return range(wally.psbt_get_num_inputs(psbt))


def _master_key(mnemonic):
    seed = wally.bip39_mnemonic_to_seed512(mnemonic, None)
    return wally.bip32_key_from_seed(seed, wally.BIP32_VER_MAIN_PRIVATE, 0)


def _public_key(bip32_key):
    return bytes(wally.bip32_key_get_pub_key(bip32_key))


def _keypath_child_numbers(keypath):
    return [int.from_bytes(keypath[offset:offset + UINT32_LEN], 'little')
            for offset in range(FINGERPRINT_LENGTH, len(keypath), UINT32_LEN)]


def _our_input_keys(psbt, input_index, master_key):
    master_fingerprint = wally.bip32_key_get_fingerprint(master_key)
    our_keys = []
    for keypath_index in range(wally.psbt_get_input_keypaths_size(psbt, input_index)):
        keypath = wally.psbt_get_input_keypath(psbt, input_index, keypath_index)
        if keypath[:FINGERPRINT_LENGTH] != master_fingerprint:
            continue
        child_key = wally.bip32_key_from_parent_path(master_key, _keypath_child_numbers(keypath),
                                                     wally.BIP32_FLAG_KEY_PRIVATE)
        assert (wally.psbt_find_input_keypath(psbt, input_index, _public_key(child_key))
                == keypath_index + 1)
        our_keys.append(child_key)
    return our_keys


def _our_input_public_keys(psbt, input_index, master_key):
    return [_public_key(our_key) for our_key in _our_input_keys(psbt, input_index, master_key)]


def _ecdsa_signers(psbt, master_key):
    return {(input_index, public_key)
            for input_index in _input_indexes(psbt)
            for public_key in _our_input_public_keys(psbt, input_index, master_key)
            if wally.psbt_find_input_signature(psbt, input_index, public_key)}


def _taproot_signed_inputs(psbt):
    return {input_index for input_index in _input_indexes(psbt)
            if wally.psbt_get_input_taproot_signature_len(psbt, input_index)}


def _signature_counts(psbt):
    return [wally.psbt_get_input_signatures_size(psbt, input_index)
            for input_index in _input_indexes(psbt)]


def _unsigned_transaction_bytes(psbt):
    transaction = wally.psbt_extract(psbt, wally.WALLY_PSBT_EXTRACT_NON_FINAL)
    return wally.tx_to_bytes(transaction, 0)


def _spent_outputs(psbt):
    spent_outputs = []
    for input_index in _input_indexes(psbt):
        utxo = wally.psbt_get_input_best_utxo(psbt, input_index)
        spent_outputs.append(TxOutput(wally.tx_output_get_satoshi(utxo),
                                      wally.tx_output_get_script(utxo)))
    return spent_outputs


def _unified_digest(psbt, input_index):
    signing_script = wally.psbt_get_input_signing_script(psbt, input_index)
    script_code = wally.psbt_get_input_scriptcode(psbt, input_index, signing_script)
    signature_type = wally.psbt_get_input_signature_type(psbt, input_index)
    transaction = parse_transaction_without_witness(_unsigned_transaction_bytes(psbt))
    return unified_sighash(transaction, input_index, _spent_outputs(psbt), script_code,
                           UNIFIED_SIGHASH_ALL, SCRIPT_TYPE_BY_SIGNATURE_TYPE[signature_type])


def _ecdsa_signature(psbt, input_index, public_key):
    signature_position = wally.psbt_find_input_signature(psbt, input_index, public_key)
    return wally.psbt_get_input_signature(psbt, input_index, signature_position - 1)


def _taproot_output_key(psbt, input_index):
    utxo_script = wally.tx_output_get_script(wally.psbt_get_input_best_utxo(psbt, input_index))
    assert wally.scriptpubkey_get_type(utxo_script) == wally.WALLY_SCRIPT_TYPE_P2TR
    return EVEN_Y_PUBLIC_KEY_PREFIX + utxo_script[P2TR_SCRIPTPUBKEY_OUTPUT_KEY_OFFSET:]


def _assert_valid_unified_ecdsa_signature(public_key, digest, signature):
    assert signature[-1] == UNIFIED_SIGHASH_ALL
    compact_signature = wally.ec_sig_from_der(signature[:-1])
    wally.ec_sig_verify(public_key, digest, wally.EC_FLAG_ECDSA, compact_signature)


def _assert_valid_unified_schnorr_signature(output_key, digest, signature):
    assert len(signature) == wally.EC_SIGNATURE_LEN + 1
    assert signature[-1] == UNIFIED_SIGHASH_ALL
    wally.ec_sig_verify(output_key, digest, wally.EC_FLAG_SCHNORR, signature[:-1])


def _assert_only_unified_ecdsa_signatures(psbt):
    for input_index in _input_indexes(psbt):
        for signature_index in range(wally.psbt_get_input_signatures_size(psbt, input_index)):
            signature = wally.psbt_get_input_signature(psbt, input_index, signature_index)
            assert signature[-1] == UNIFIED_SIGHASH_ALL


def _assert_declared_sighashes(psbt, signed_psbt, signed_inputs):
    for input_index in _input_indexes(psbt):
        expected_sighash = (UNIFIED_SIGHASH_ALL if input_index in signed_inputs
                            else wally.psbt_get_input_sighash(psbt, input_index))
        assert wally.psbt_get_input_sighash(signed_psbt, input_index) == expected_sighash


def _assert_unified_signatures(psbt_bytes, signed_psbt_bytes, bitcoin_signed_psbt_bytes, mnemonic):
    master_key = _master_key(mnemonic)
    psbt = wally.psbt_from_bytes(psbt_bytes, 0)
    signed_psbt = wally.psbt_from_bytes(signed_psbt_bytes, 0)
    bitcoin_signed_psbt = wally.psbt_from_bytes(bitcoin_signed_psbt_bytes, 0)

    assert _unsigned_transaction_bytes(signed_psbt) == _unsigned_transaction_bytes(psbt)
    assert _signature_counts(signed_psbt) == _signature_counts(bitcoin_signed_psbt)
    ecdsa_signers = _ecdsa_signers(signed_psbt, master_key)
    taproot_signed_inputs = _taproot_signed_inputs(signed_psbt)
    assert ecdsa_signers == _ecdsa_signers(bitcoin_signed_psbt, master_key)
    assert taproot_signed_inputs == _taproot_signed_inputs(bitcoin_signed_psbt)

    _assert_only_unified_ecdsa_signatures(signed_psbt)
    for input_index, public_key in ecdsa_signers:
        _assert_valid_unified_ecdsa_signature(
            public_key, _unified_digest(psbt, input_index),
            _ecdsa_signature(signed_psbt, input_index, public_key))
    for input_index in taproot_signed_inputs:
        _assert_valid_unified_schnorr_signature(
            _taproot_output_key(psbt, input_index), _unified_digest(psbt, input_index),
            wally.psbt_get_input_taproot_signature(signed_psbt, input_index))

    ecdsa_signed_inputs = {input_index for input_index, _ in ecdsa_signers}
    _assert_declared_sighashes(psbt, signed_psbt, ecdsa_signed_inputs | taproot_signed_inputs)


def _check_fixture_signed_with_unified_sighash(jade, fixture, mnemonic):
    signed_psbt_bytes = jade.sign_psbt(fixture.network, fixture.psbt_bytes)
    _assert_unified_signatures(fixture.psbt_bytes, signed_psbt_bytes,
                               fixture.bitcoin_signed_psbt_bytes, mnemonic)


def _sign_psbt_rpc_arguments(request_id, network, psbt_bytes):
    return (request_id, 'sign_psbt', {'network': network, 'psbt': psbt_bytes})


def _check_sign_psbt_bad_parameters(jade, request_id, network, psbt_bytes,
                                    expected_error_message):
    check_bad_params(jade.jade, _sign_psbt_rpc_arguments(request_id, network, psbt_bytes),
                     expected_error_message)


def _check_sign_psbt_internal_error(jade, request_id, network, psbt_bytes,
                                    expected_error_message):
    sign_psbt_request = jade.jade.build_request(
        *_sign_psbt_rpc_arguments(request_id, network, psbt_bytes))
    sign_psbt_reply = jade.jade.make_rpc_call(sign_psbt_request)
    assert sign_psbt_reply['id'] == sign_psbt_request['id']
    assert 'result' not in sign_psbt_reply
    assert sign_psbt_reply['error']['code'] == JadeError.INTERNAL_ERROR
    assert sign_psbt_reply['error']['message'] == expected_error_message


def _check_fixture_rejected_for_non_unified_signature(jade, fixture):
    _check_sign_psbt_bad_parameters(jade, NON_UNIFIED_SIGNATURE_REQUEST_ID, fixture.network,
                                    fixture.psbt_bytes, NON_UNIFIED_SIGNATURE_ERROR_MESSAGE)


def _check_fixture_rejected_for_multisig_input(jade, fixture):
    _check_sign_psbt_bad_parameters(jade, NON_SINGLESIG_INPUT_REQUEST_ID, fixture.network,
                                    fixture.psbt_bytes, NON_SINGLESIG_INPUT_ERROR_MESSAGE)


def _with_declared_sighash(psbt_bytes, declared_sighash):
    psbt = wally.psbt_from_bytes(psbt_bytes, 0)
    for input_index in _input_indexes(psbt):
        wally.psbt_set_input_sighash(psbt, input_index, declared_sighash)
    return wally.psbt_to_bytes(psbt, 0)


def _with_our_unified_signature_over_another_digest(psbt_bytes, input_index, mnemonic):
    psbt = wally.psbt_from_bytes(psbt_bytes, 0)
    [our_key] = _our_input_keys(psbt, input_index, _master_key(mnemonic))
    compact_signature = wally.ec_sig_from_bytes(wally.bip32_key_get_priv_key(our_key),
                                                ANOTHER_TRANSACTION_DIGEST,
                                                wally.EC_FLAG_ECDSA | wally.EC_FLAG_GRIND_R)
    signature = wally.ec_sig_to_der(compact_signature) + bytes([UNIFIED_SIGHASH_ALL])
    wally.psbt_add_input_signature(psbt, input_index, _public_key(our_key), signature)
    return wally.psbt_to_bytes(psbt, 0)


def _with_bitcoin_taproot_signature(psbt_bytes, bitcoin_signed_psbt_bytes, input_index):
    psbt = wally.psbt_from_bytes(psbt_bytes, 0)
    bitcoin_signed_psbt = wally.psbt_from_bytes(bitcoin_signed_psbt_bytes, 0)
    bitcoin_signature = wally.psbt_get_input_taproot_signature(bitcoin_signed_psbt, input_index)
    wally.psbt_set_input_taproot_signature(psbt, input_index, bitcoin_signature)
    return wally.psbt_to_bytes(psbt, 0)


def _with_other_wallet_input(psbt_bytes, input_index):
    psbt = wally.psbt_from_bytes(psbt_bytes, 0)
    wally.psbt_set_input_keypaths(psbt, input_index, wally.map_init(0, None))
    return wally.psbt_to_bytes(psbt, 0)


def _with_other_wallet_input_missing_utxo(psbt_bytes, input_index):
    psbt = wally.psbt_from_bytes(_with_other_wallet_input(psbt_bytes, input_index), 0)
    wally.psbt_set_input_witness_utxo(psbt, input_index, None)
    wally.psbt_set_input_utxo(psbt, input_index, None)
    return wally.psbt_to_bytes(psbt, 0)


@pytest.mark.mnemonic(mnemonics.singlesig)
@pytest.mark.parametrize('fixture', _fixture_parameters(SINGLESIG_MNEMONIC_FIXTURES))
def test_xbt_signs_singlesig_mnemonic_psbt_with_unified_sighash(jade, mnemonic, fixture):
    _check_fixture_signed_with_unified_sighash(jade, fixture, mnemonics.singlesig)


@pytest.mark.mnemonic(mnemonics.default)
@pytest.mark.parametrize('fixture', _fixture_parameters(DEFAULT_MNEMONIC_FIXTURES))
def test_xbt_signs_default_mnemonic_psbt_with_unified_sighash(jade, mnemonic, fixture):
    _check_fixture_signed_with_unified_sighash(jade, fixture, mnemonics.default)


@pytest.mark.mnemonic(mnemonics.singlesig)
@pytest.mark.parametrize('declared_sighash', SUPPORTED_DECLARED_SIGHASHES, ids=hex)
def test_xbt_signs_psbt_declaring_supported_sighash(jade, mnemonic, declared_sighash):
    fixture = _load_fixture(DECLARED_SIGHASH_FIXTURE)
    psbt_bytes = _with_declared_sighash(fixture.psbt_bytes, declared_sighash)
    signed_psbt_bytes = jade.sign_psbt(fixture.network, psbt_bytes)
    _assert_unified_signatures(psbt_bytes, signed_psbt_bytes, fixture.bitcoin_signed_psbt_bytes,
                               mnemonics.singlesig)


@pytest.mark.mnemonic(mnemonics.singlesig)
@pytest.mark.parametrize('declared_sighash', UNSUPPORTED_DECLARED_SIGHASHES, ids=hex)
def test_xbt_rejects_psbt_declaring_unsupported_sighash(jade, mnemonic, declared_sighash):
    fixture = _load_fixture(DECLARED_SIGHASH_FIXTURE)
    psbt_bytes = _with_declared_sighash(fixture.psbt_bytes, declared_sighash)
    _check_sign_psbt_bad_parameters(jade, UNSUPPORTED_SIGHASH_REQUEST_ID, fixture.network,
                                    psbt_bytes, UNSUPPORTED_SIGHASH_ERROR_MESSAGE)


@pytest.mark.mnemonic(mnemonics.singlesig)
@pytest.mark.parametrize(
    'fixture', _fixture_parameters(SINGLESIG_MNEMONIC_FIXTURES_WITH_NON_UNIFIED_SIGNATURE))
def test_xbt_rejects_singlesig_mnemonic_psbt_with_non_unified_signature(jade, mnemonic, fixture):
    _check_fixture_rejected_for_non_unified_signature(jade, fixture)


@pytest.mark.mnemonic(mnemonics.singlesig)
@pytest.mark.parametrize(
    'fixture', _fixture_parameters(SINGLESIG_MNEMONIC_FIXTURES_WITH_MULTISIG_INPUT))
def test_xbt_rejects_singlesig_mnemonic_psbt_with_multisig_input(jade, mnemonic, fixture):
    _check_fixture_rejected_for_multisig_input(jade, fixture)


@pytest.mark.mnemonic(mnemonics.default)
@pytest.mark.parametrize(
    'fixture', _fixture_parameters(DEFAULT_MNEMONIC_FIXTURES_WITH_MULTISIG_INPUT))
def test_xbt_rejects_default_mnemonic_psbt_with_multisig_input(jade, mnemonic, fixture):
    _check_fixture_rejected_for_multisig_input(jade, fixture)


@pytest.mark.mnemonic(mnemonics.singlesig)
def test_xbt_ignores_other_wallet_multisig_input(jade, mnemonic):
    fixture = _load_fixture(OTHER_WALLET_MULTISIG_FIXTURE)
    psbt_bytes = _with_other_wallet_input(fixture.psbt_bytes, OTHER_WALLET_MULTISIG_INPUT_INDEX)
    signed_psbt_bytes = jade.sign_psbt(fixture.network, psbt_bytes)
    psbt = wally.psbt_from_bytes(psbt_bytes, 0)
    signed_psbt = wally.psbt_from_bytes(signed_psbt_bytes, 0)
    assert _signature_counts(signed_psbt) == _signature_counts(psbt)
    _assert_declared_sighashes(psbt, signed_psbt, signed_inputs=set())


@pytest.mark.mnemonic(mnemonics.singlesig)
@pytest.mark.parametrize('input_index', BITCOIN_TAPROOT_SIGNATURE_INPUT_INDEX_PARAMETERS)
def test_xbt_rejects_taproot_psbt_with_non_unified_signature(jade, mnemonic, input_index):
    fixture = _load_fixture(BITCOIN_TAPROOT_SIGNATURE_FIXTURE)
    psbt_bytes = _with_bitcoin_taproot_signature(fixture.psbt_bytes,
                                                 fixture.bitcoin_signed_psbt_bytes, input_index)
    _check_sign_psbt_bad_parameters(jade, NON_UNIFIED_SIGNATURE_REQUEST_ID, fixture.network,
                                    psbt_bytes, NON_UNIFIED_SIGNATURE_ERROR_MESSAGE)


@pytest.mark.mnemonic(mnemonics.singlesig)
@pytest.mark.parametrize('fixture', _fixture_parameters(SIGNED_TWICE_FIXTURES))
def test_xbt_signs_psbt_with_unified_signature(jade, mnemonic, fixture):
    signed_psbt_bytes = jade.sign_psbt(fixture.network, fixture.psbt_bytes)
    signed_again_psbt_bytes = jade.sign_psbt(fixture.network, signed_psbt_bytes)
    _assert_unified_signatures(fixture.psbt_bytes, signed_again_psbt_bytes,
                               fixture.bitcoin_signed_psbt_bytes, mnemonics.singlesig)


@pytest.mark.mnemonic(mnemonics.singlesig)
def test_xbt_rejects_psbt_with_our_unified_signature_over_another_digest(jade, mnemonic):
    fixture = _load_fixture(SIGNATURE_OVER_ANOTHER_DIGEST_FIXTURE)
    psbt_bytes = _with_our_unified_signature_over_another_digest(
        fixture.psbt_bytes, SIGNATURE_OVER_ANOTHER_DIGEST_INPUT_INDEX, mnemonics.singlesig)
    _check_sign_psbt_internal_error(jade, SIGNATURE_OVER_ANOTHER_DIGEST_REQUEST_ID,
                                    fixture.network, psbt_bytes,
                                    UNIFIED_SIGNATURE_VERIFICATION_ERROR_MESSAGE)


@pytest.mark.mnemonic(mnemonics.singlesig)
def test_xbt_rejects_psbt_with_other_wallet_input_missing_utxo(jade, mnemonic):
    fixture = _load_fixture(MISSING_UTXO_FIXTURE)
    psbt_bytes = _with_other_wallet_input_missing_utxo(fixture.psbt_bytes, MISSING_UTXO_INPUT_INDEX)
    _check_sign_psbt_bad_parameters(jade, MISSING_UTXO_REQUEST_ID, fixture.network, psbt_bytes,
                                    MISSING_UTXO_ERROR_MESSAGE)

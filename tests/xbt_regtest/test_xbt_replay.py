from collections import namedtuple

from . import *
from ..rpc.unified_sighash_reference import SIGHASH_ALL, SIGHASH_UNIFIED

pytestmark = xbt_replay_only

UNIFIED_SIGHASH_ALL = SIGHASH_ALL | SIGHASH_UNIFIED
KNOTS_RPC_PORT = 18463
BITCOIN_CORE_RPC_PORT = 18453
SHARED_HISTORY_HEIGHT = 110
POST_ACTIVATION_HEIGHT = BLAKE2B_ACTIVATION_HEIGHT + 5
COINBASE_OUTPUT_NUMBER = 0
NO_LOCKTIME = 0
PAYMENT_AMOUNT_XBT = 10
VALIDATE_WITHOUT_SUBMITTING = 'false'
ECDSA_MEMPOOL_REJECT_REASON = ('mempool-script-verify-flag-failed '
                               '(Signature hash type missing or not understood)')
ECDSA_BLOCK_REJECT_REASON = ('block-script-verify-flag-failed (Script evaluated without error '
                             'but finished with a false/empty top stack element)')
SCHNORR_MEMPOOL_REJECT_REASON = ('mempool-script-verify-flag-failed '
                                 '(Invalid Schnorr signature hash type)')
SCHNORR_BLOCK_REJECT_REASON = ('block-script-verify-flag-failed '
                               '(Invalid Schnorr signature hash type)')

ReplayCase = namedtuple('ReplayCase',
                        ['account_type', 'mempool_reject_reason', 'block_reject_reason'])
SharedHistory = namedtuple('SharedHistory',
                           ['miner_address', 'nefrita_coinbase_transaction_ids'])

REPLAY_CASES = [
    ReplayCase(P2PKH_ACCOUNT, ECDSA_MEMPOOL_REJECT_REASON, ECDSA_BLOCK_REJECT_REASON),
    ReplayCase(P2SH_P2WPKH_ACCOUNT, ECDSA_MEMPOOL_REJECT_REASON, ECDSA_BLOCK_REJECT_REASON),
    ReplayCase(P2WPKH_ACCOUNT, ECDSA_MEMPOOL_REJECT_REASON, ECDSA_BLOCK_REJECT_REASON),
    ReplayCase(P2TR_ACCOUNT, SCHNORR_MEMPOOL_REJECT_REASON, SCHNORR_BLOCK_REJECT_REASON),
]


@pytest.fixture(scope='module')
def knots_node(tmp_path_factory):
    with RegtestNode(KNOTS_BINARY_DIRECTORY, tmp_path_factory.mktemp('knots_replay'),
                     KNOTS_RPC_PORT, KNOTS_BITCOIND_OPTIONS) as knots_node:
        yield knots_node


@pytest.fixture(scope='module')
def bitcoin_core_node(tmp_path_factory):
    with RegtestNode(BITCOIN_CORE_BINARY_DIRECTORY, tmp_path_factory.mktemp('bitcoin_core_replay'),
                     BITCOIN_CORE_RPC_PORT) as bitcoin_core_node:
        yield bitcoin_core_node


@pytest.fixture(scope='module')
def jade_with_default_mnemonic(jade):
    get_jade_config().set_mnemonic(mnemonics.default)
    return jade


def _tip_coinbase_transaction_id(knots_node):
    tip_block = knots_node.bitcoin_cli_json('getblock', knots_node.bitcoin_cli('getbestblockhash'))
    return tip_block['tx'][0]


def _copy_blocks(source_node, destination_node, last_height):
    for height in range(1, last_height + 1):
        block_hash = source_node.bitcoin_cli('getblockhash', str(height))
        block_hex = source_node.bitcoin_cli('getblock', block_hash, '0')
        block_reject_reason = destination_node.bitcoin_cli('submitblock', block_hex)
        assert block_reject_reason == '', (height, block_reject_reason)


@pytest.fixture(scope='module')
def shared_history(jade_with_default_mnemonic, knots_node, bitcoin_core_node):
    create_miner_wallet(knots_node)
    miner_address = new_miner_address(knots_node)
    create_nefrita_watch_only_wallet(knots_node, jade_with_default_mnemonic, MVP_ACCOUNT_TYPES)
    nefrita_coinbase_transaction_ids = {}
    for account_type in MVP_ACCOUNT_TYPES:
        knots_node.mine_blocks(1, new_nefrita_address(knots_node, account_type))
        nefrita_coinbase_transaction_ids[account_type.script_type] = (
            _tip_coinbase_transaction_id(knots_node))
    knots_node.mine_blocks(SHARED_HISTORY_HEIGHT - len(MVP_ACCOUNT_TYPES), miner_address)

    _copy_blocks(knots_node, bitcoin_core_node, SHARED_HISTORY_HEIGHT)
    assert (bitcoin_core_node.bitcoin_cli('getbestblockhash')
            == knots_node.bitcoin_cli('getblockhash', str(SHARED_HISTORY_HEIGHT)))

    knots_node.mine_blocks(POST_ACTIVATION_HEIGHT - SHARED_HISTORY_HEIGHT, miner_address)
    assert_blake2b_active(knots_node)
    return SharedHistory(miner_address, nefrita_coinbase_transaction_ids)


def _create_coinbase_spend_psbt_base64(knots_node, shared_history, account_type):
    coinbase_transaction_id = shared_history.nefrita_coinbase_transaction_ids[
        account_type.script_type]
    coinbase_input = [{'txid': coinbase_transaction_id, 'vout': COINBASE_OUTPUT_NUMBER}]
    payment_output = [{shared_history.miner_address: PAYMENT_AMOUNT_XBT}]
    funding_options = {'add_inputs': False, 'change_type': account_type.address_type}
    return knots_node.bitcoin_cli_json(
        NEFRITA_WALLET_ARGUMENT, '-named', 'walletcreatefundedpsbt',
        f'inputs={json.dumps(coinbase_input)}', f'outputs={json.dumps(payment_output)}',
        f'locktime={NO_LOCKTIME}', f'options={json.dumps(funding_options)}')['psbt']


def _bitcoin_signed_psbt_bytes(psbt_base64):
    psbt = wally.psbt_from_base64(psbt_base64, 0)
    seed = wally.bip39_mnemonic_to_seed512(mnemonics.default, None)
    master_bip32_key = wally.bip32_key_from_seed(seed, wally.BIP32_VER_TEST_PRIVATE, 0)
    wally.psbt_sign_bip32(psbt, master_bip32_key, 0)
    return wally.psbt_to_bytes(psbt, 0)


def _first_input_signature(knots_node, transaction_hex):
    [first_input] = knots_node.bitcoin_cli_json('decoderawtransaction', transaction_hex)['vin']
    if 'txinwitness' in first_input:
        return bytes.fromhex(first_input['txinwitness'][0])
    script_sig = bytes.fromhex(first_input['scriptSig']['hex'])
    signature_length = script_sig[0]
    return script_sig[1:1 + signature_length]


def _block_validation_error_message(bitcoin_core_node, shared_history, transaction_hex):
    return bitcoin_core_node.bitcoin_cli_error_message(
        'generateblock', shared_history.miner_address, json.dumps([transaction_hex]),
        VALIDATE_WITHOUT_SUBMITTING)


def _assert_block_accepts(bitcoin_core_node, shared_history, transaction_hex):
    validated_block = bitcoin_core_node.bitcoin_cli_json(
        'generateblock', shared_history.miner_address, json.dumps([transaction_hex]),
        VALIDATE_WITHOUT_SUBMITTING)
    assert validated_block['hex']


@pytest.mark.mnemonic(mnemonics.default)
@pytest.mark.parametrize('replay_case', [
    pytest.param(replay_case, id=replay_case.account_type.script_type)
    for replay_case in REPLAY_CASES])
def test_bitcoin_core_rejects_xbt_signature_that_knots_accepts(
        jade, mnemonic, knots_node, bitcoin_core_node, shared_history, replay_case):
    psbt_base64 = _create_coinbase_spend_psbt_base64(knots_node, shared_history,
                                                     replay_case.account_type)
    xbt_signed_psbt_bytes = jade.sign_psbt(XBT_REGTEST_NETWORK, base64.b64decode(psbt_base64))
    xbt_transaction_hex = finalize_psbt(knots_node, xbt_signed_psbt_bytes)
    bitcoin_transaction_hex = finalize_psbt(knots_node, _bitcoin_signed_psbt_bytes(psbt_base64))
    assert _first_input_signature(knots_node, xbt_transaction_hex)[-1] == UNIFIED_SIGHASH_ALL

    assert_mempool_accepts(knots_node, xbt_transaction_hex)

    xbt_transaction_acceptance_by_bitcoin_core = mempool_acceptance(bitcoin_core_node,
                                                                    xbt_transaction_hex)
    assert (xbt_transaction_acceptance_by_bitcoin_core.get('reject-reason')
            == replay_case.mempool_reject_reason), xbt_transaction_acceptance_by_bitcoin_core
    assert (f'TestBlockValidity failed: {replay_case.block_reject_reason}'
            in _block_validation_error_message(bitcoin_core_node, shared_history,
                                               xbt_transaction_hex))

    assert_mempool_accepts(bitcoin_core_node, bitcoin_transaction_hex)
    _assert_block_accepts(bitcoin_core_node, shared_history, bitcoin_transaction_hex)

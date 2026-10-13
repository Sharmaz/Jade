from . import *
from ..rpc.unified_sighash_reference import SIGHASH_ALL, SIGHASH_UNIFIED

pytestmark = xbt_knots_regtest_only

UNIFIED_SIGHASH_ALL = SIGHASH_ALL | SIGHASH_UNIFIED
KNOTS_RPC_PORT = 18443
CHAIN_HEIGHT_WITH_MATURE_COINBASES = 210
NEFRITA_FUNDING_AMOUNT_XBT = 1
PAYMENT_AMOUNT_XBT = 0.5


@pytest.fixture(scope='module')
def knots_node(tmp_path_factory):
    with RegtestNode(KNOTS_BINARY_DIRECTORY, tmp_path_factory.mktemp('knots_regtest'),
                     KNOTS_RPC_PORT, KNOTS_BITCOIND_OPTIONS) as knots_node:
        yield knots_node


def _mine_past_blake2b_activation(knots_node):
    create_miner_wallet(knots_node)
    miner_address = new_miner_address(knots_node)
    knots_node.mine_blocks(CHAIN_HEIGHT_WITH_MATURE_COINBASES, miner_address)
    assert_blake2b_active(knots_node)
    return miner_address


def _fund_nefrita(knots_node, miner_address):
    nefrita_address = new_nefrita_address(knots_node, P2WPKH_ACCOUNT)
    knots_node.bitcoin_cli(MINER_WALLET_ARGUMENT, 'sendtoaddress', nefrita_address,
                           str(NEFRITA_FUNDING_AMOUNT_XBT))
    knots_node.mine_blocks(1, miner_address)


def _create_nefrita_payment_psbt_base64(knots_node):
    payment_address = knots_node.bitcoin_cli(MINER_WALLET_ARGUMENT, '-named', 'getnewaddress',
                                             'address_type=bech32')
    payment_outputs = json.dumps([{payment_address: PAYMENT_AMOUNT_XBT}])
    return knots_node.bitcoin_cli_json(NEFRITA_WALLET_ARGUMENT, '-named', 'walletcreatefundedpsbt',
                                       f'outputs={payment_outputs}')['psbt']


def _finalize_and_check_mempool_acceptance(knots_node, signed_psbt_bytes):
    transaction_hex = finalize_psbt(knots_node, signed_psbt_bytes)
    assert_mempool_accepts(knots_node, transaction_hex)
    return transaction_hex


def _assert_unified_witness_signatures(knots_node, transaction_hex):
    decoded_transaction = knots_node.bitcoin_cli_json('decoderawtransaction', transaction_hex)
    for transaction_input in decoded_transaction['vin']:
        witness_signature = bytes.fromhex(transaction_input['txinwitness'][0])
        assert witness_signature[-1] == UNIFIED_SIGHASH_ALL


@pytest.mark.mnemonic(mnemonics.default)
def test_xbt_signs_knots_psbt_accepted_by_knots_regtest(jade, mnemonic, knots_node):
    miner_address = _mine_past_blake2b_activation(knots_node)
    create_nefrita_watch_only_wallet(knots_node, jade, [P2WPKH_ACCOUNT])
    _fund_nefrita(knots_node, miner_address)

    payment_psbt_base64 = _create_nefrita_payment_psbt_base64(knots_node)
    signed_psbt_bytes = jade.sign_psbt(XBT_REGTEST_NETWORK, base64.b64decode(payment_psbt_base64))
    transaction_hex = _finalize_and_check_mempool_acceptance(knots_node, signed_psbt_bytes)
    transaction_id = knots_node.bitcoin_cli('sendrawtransaction', transaction_hex)
    knots_node.mine_blocks(1, miner_address)

    nefrita_transaction = knots_node.bitcoin_cli_json(NEFRITA_WALLET_ARGUMENT, 'gettransaction',
                                                      transaction_id)
    assert nefrita_transaction['confirmations'] == 1
    _assert_unified_witness_signatures(knots_node, transaction_hex)

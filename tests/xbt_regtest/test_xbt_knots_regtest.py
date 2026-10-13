from . import *
from ..rpc.unified_sighash_reference import SIGHASH_ALL, SIGHASH_UNIFIED

pytestmark = xbt_knots_regtest_only

UNIFIED_SIGHASH_ALL = SIGHASH_ALL | SIGHASH_UNIFIED
XBT_REGTEST_NETWORK = 'xbt-regtest'
BLAKE2B_ACTIVATION_HEIGHT = 200
CHAIN_HEIGHT_WITH_MATURE_COINBASES = 210
FALLBACK_FEE_XBT_PER_VIRTUAL_KILOBYTE = '0.0001'
NODE_START_TIMEOUT_SECONDS = 60
NODE_STOP_TIMEOUT_SECONDS = 60
MINER_WALLET_NAME = 'miner'
NEFRITA_WALLET_NAME = 'nefrita'
MINER_WALLET_ARGUMENT = f'-rpcwallet={MINER_WALLET_NAME}'
NEFRITA_WALLET_ARGUMENT = f'-rpcwallet={NEFRITA_WALLET_NAME}'
NEFRITA_FUNDING_AMOUNT_XBT = 1
PAYMENT_AMOUNT_XBT = 0.5
DESCRIPTOR_RANGE = [0, 100]
HARDENED = 0x80000000
BIP84_PURPOSE = 84 | HARDENED
TESTNET_COIN_TYPE = 1 | HARDENED
FIRST_ACCOUNT = 0 | HARDENED
ACCOUNT_PATH = [BIP84_PURPOSE, TESTNET_COIN_TYPE, FIRST_ACCOUNT]
ACCOUNT_ORIGIN_PATH = '84h/1h/0h'
EXTERNAL_CHAIN = 0
INTERNAL_CHAIN = 1


class KnotsRegtestNode:
    def __init__(self, data_directory):
        self.data_directory = data_directory

    def bitcoin_cli(self, *arguments):
        bitcoin_cli_path = os.path.join(KNOTS_BINARY_DIRECTORY, 'bitcoin-cli')
        completed_process = subprocess.run(
            [bitcoin_cli_path, '-regtest', f'-datadir={self.data_directory}', *arguments],
            capture_output=True, text=True)
        assert completed_process.returncode == 0, completed_process.stderr
        return completed_process.stdout.strip()

    def bitcoin_cli_json(self, *arguments):
        return json.loads(self.bitcoin_cli(*arguments))


@pytest.fixture(scope='module')
def knots_node(tmp_path_factory):
    data_directory = tmp_path_factory.mktemp('knots_regtest')
    bitcoind_path = os.path.join(KNOTS_BINARY_DIRECTORY, 'bitcoind')
    node_process = subprocess.Popen([
        bitcoind_path, '-regtest', f'-datadir={data_directory}', '-listen=0',
        f'-fallbackfee={FALLBACK_FEE_XBT_PER_VIRTUAL_KILOBYTE}',
        f'-testactivationheight=blake2b@{BLAKE2B_ACTIVATION_HEIGHT}'])
    knots_node = KnotsRegtestNode(data_directory)
    knots_node.bitcoin_cli('-rpcwait', f'-rpcwaittimeout={NODE_START_TIMEOUT_SECONDS}',
                           'getblockcount')
    yield knots_node
    knots_node.bitcoin_cli('stop')
    node_process.wait(timeout=NODE_STOP_TIMEOUT_SECONDS)


def _mine_blocks(knots_node, block_count, miner_address):
    knots_node.bitcoin_cli('generatetoaddress', str(block_count), miner_address)


def _mine_past_blake2b_activation(knots_node):
    knots_node.bitcoin_cli('-named', 'createwallet', f'wallet_name={MINER_WALLET_NAME}')
    miner_address = knots_node.bitcoin_cli(MINER_WALLET_ARGUMENT, 'getnewaddress')
    _mine_blocks(knots_node, CHAIN_HEIGHT_WITH_MATURE_COINBASES, miner_address)
    blake2b_hardfork_schedule = knots_node.bitcoin_cli_json('getdeploymentinfo')['blake2b']
    assert blake2b_hardfork_schedule['active']
    assert blake2b_hardfork_schedule['height'] == BLAKE2B_ACTIVATION_HEIGHT
    return miner_address


def _account_descriptors(jade):
    master_xpub = jade.get_xpub(XBT_REGTEST_NETWORK, [])
    account_xpub = jade.get_xpub(XBT_REGTEST_NETWORK, ACCOUNT_PATH)
    master_bip32_key = wally.bip32_key_from_base58(master_xpub)
    master_fingerprint = wally.bip32_key_get_fingerprint(master_bip32_key).hex()
    account_key_with_origin = f'[{master_fingerprint}/{ACCOUNT_ORIGIN_PATH}]{account_xpub}'
    return (f'wpkh({account_key_with_origin}/{EXTERNAL_CHAIN}/*)',
            f'wpkh({account_key_with_origin}/{INTERNAL_CHAIN}/*)')


def _descriptor_with_checksum(knots_node, descriptor):
    checksum = knots_node.bitcoin_cli_json('getdescriptorinfo', descriptor)['checksum']
    return f'{descriptor}#{checksum}'


def _create_nefrita_watch_only_wallet(knots_node, jade):
    external_descriptor, internal_descriptor = _account_descriptors(jade)
    knots_node.bitcoin_cli('-named', 'createwallet', f'wallet_name={NEFRITA_WALLET_NAME}',
                           'disable_private_keys=true', 'blank=true')
    descriptor_imports = [
        {'desc': _descriptor_with_checksum(knots_node, external_descriptor), 'active': True,
         'internal': False, 'range': DESCRIPTOR_RANGE, 'timestamp': 'now'},
        {'desc': _descriptor_with_checksum(knots_node, internal_descriptor), 'active': True,
         'internal': True, 'range': DESCRIPTOR_RANGE, 'timestamp': 'now'},
    ]
    import_results = knots_node.bitcoin_cli_json(NEFRITA_WALLET_ARGUMENT, 'importdescriptors',
                                                 json.dumps(descriptor_imports))
    assert all(import_result['success'] for import_result in import_results), import_results


def _fund_nefrita(knots_node, miner_address):
    nefrita_address = knots_node.bitcoin_cli(NEFRITA_WALLET_ARGUMENT, '-named', 'getnewaddress',
                                             'address_type=bech32')
    knots_node.bitcoin_cli(MINER_WALLET_ARGUMENT, 'sendtoaddress', nefrita_address,
                           str(NEFRITA_FUNDING_AMOUNT_XBT))
    _mine_blocks(knots_node, 1, miner_address)


def _create_nefrita_payment_psbt_base64(knots_node):
    payment_address = knots_node.bitcoin_cli(MINER_WALLET_ARGUMENT, '-named', 'getnewaddress',
                                             'address_type=bech32')
    payment_outputs = json.dumps([{payment_address: PAYMENT_AMOUNT_XBT}])
    return knots_node.bitcoin_cli_json(NEFRITA_WALLET_ARGUMENT, '-named', 'walletcreatefundedpsbt',
                                       f'outputs={payment_outputs}')['psbt']


def _finalize_and_check_mempool_acceptance(knots_node, signed_psbt_bytes):
    signed_psbt_base64 = base64.b64encode(signed_psbt_bytes).decode()
    psbt_finalization = knots_node.bitcoin_cli_json('finalizepsbt', signed_psbt_base64)
    assert psbt_finalization['complete'], psbt_finalization
    transaction_hex = psbt_finalization['hex']
    [mempool_acceptance] = knots_node.bitcoin_cli_json('testmempoolaccept',
                                                       json.dumps([transaction_hex]))
    assert mempool_acceptance['allowed'], mempool_acceptance
    return transaction_hex


def _assert_unified_witness_signatures(knots_node, transaction_hex):
    decoded_transaction = knots_node.bitcoin_cli_json('decoderawtransaction', transaction_hex)
    for transaction_input in decoded_transaction['vin']:
        witness_signature = bytes.fromhex(transaction_input['txinwitness'][0])
        assert witness_signature[-1] == UNIFIED_SIGHASH_ALL


@pytest.mark.mnemonic(mnemonics.default)
def test_xbt_signs_knots_psbt_accepted_by_knots_regtest(jade, mnemonic, knots_node):
    miner_address = _mine_past_blake2b_activation(knots_node)
    _create_nefrita_watch_only_wallet(knots_node, jade)
    _fund_nefrita(knots_node, miner_address)

    payment_psbt_base64 = _create_nefrita_payment_psbt_base64(knots_node)
    signed_psbt_bytes = jade.sign_psbt(XBT_REGTEST_NETWORK, base64.b64decode(payment_psbt_base64))
    transaction_hex = _finalize_and_check_mempool_acceptance(knots_node, signed_psbt_bytes)
    transaction_id = knots_node.bitcoin_cli('sendrawtransaction', transaction_hex)
    _mine_blocks(knots_node, 1, miner_address)

    nefrita_transaction = knots_node.bitcoin_cli_json(NEFRITA_WALLET_ARGUMENT, 'gettransaction',
                                                      transaction_id)
    assert nefrita_transaction['confirmations'] == 1
    _assert_unified_witness_signatures(knots_node, transaction_hex)

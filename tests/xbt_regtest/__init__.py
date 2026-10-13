from collections import namedtuple

from .. import *
from ..xbt import is_xbt_firmware

KNOTS_BINARY_DIRECTORY = os.environ.get('KNOTS_BINARY_DIRECTORY')
BITCOIN_CORE_BINARY_DIRECTORY = os.environ.get('BITCOIN_CORE_BINARY_DIRECTORY')

xbt_knots_regtest_only = pytest.mark.skipif(
    not is_xbt_firmware() or not KNOTS_BINARY_DIRECTORY,
    reason='requires an XBT firmware and KNOTS_BINARY_DIRECTORY')

xbt_replay_only = pytest.mark.skipif(
    not is_xbt_firmware() or not KNOTS_BINARY_DIRECTORY or not BITCOIN_CORE_BINARY_DIRECTORY,
    reason='requires an XBT firmware, KNOTS_BINARY_DIRECTORY and BITCOIN_CORE_BINARY_DIRECTORY')

XBT_REGTEST_NETWORK = 'xbt-regtest'
BLAKE2B_ACTIVATION_HEIGHT = 200
FALLBACK_FEE_XBT_PER_VIRTUAL_KILOBYTE = '0.0001'
KNOTS_BITCOIND_OPTIONS = (f'-fallbackfee={FALLBACK_FEE_XBT_PER_VIRTUAL_KILOBYTE}',
                          f'-testactivationheight=blake2b@{BLAKE2B_ACTIVATION_HEIGHT}')
NODE_START_TIMEOUT_SECONDS = 60
NODE_STOP_TIMEOUT_SECONDS = 60
MINER_WALLET_NAME = 'miner'
NEFRITA_WALLET_NAME = 'nefrita'
MINER_WALLET_ARGUMENT = f'-rpcwallet={MINER_WALLET_NAME}'
NEFRITA_WALLET_ARGUMENT = f'-rpcwallet={NEFRITA_WALLET_NAME}'
DESCRIPTOR_RANGE = [0, 100]
HARDENED = 0x80000000
TESTNET_COIN_TYPE = 1 | HARDENED
FIRST_ACCOUNT = 0 | HARDENED
EXTERNAL_CHAIN = 0
INTERNAL_CHAIN = 1

AccountType = namedtuple('AccountType',
                         ['script_type', 'purpose', 'descriptor_template', 'address_type'])

P2PKH_ACCOUNT = AccountType('p2pkh', 44, 'pkh({})', 'legacy')
P2SH_P2WPKH_ACCOUNT = AccountType('p2sh-p2wpkh', 49, 'sh(wpkh({}))', 'p2sh-segwit')
P2WPKH_ACCOUNT = AccountType('p2wpkh', 84, 'wpkh({})', 'bech32')
P2TR_ACCOUNT = AccountType('p2tr', 86, 'tr({})', 'bech32m')
MVP_ACCOUNT_TYPES = [P2PKH_ACCOUNT, P2SH_P2WPKH_ACCOUNT, P2WPKH_ACCOUNT, P2TR_ACCOUNT]


class RegtestNode:
    def __init__(self, binary_directory, data_directory, rpc_port, bitcoind_options=()):
        self.binary_directory = binary_directory
        self.data_directory = data_directory
        self.rpc_port = rpc_port
        self.bitcoind_options = bitcoind_options
        self.bitcoind_process = None

    def __enter__(self):
        bitcoind_path = os.path.join(self.binary_directory, 'bitcoind')
        self.bitcoind_process = subprocess.Popen([
            bitcoind_path, '-regtest', f'-datadir={self.data_directory}',
            f'-rpcport={self.rpc_port}', '-listen=0', *self.bitcoind_options])
        self.bitcoin_cli('-rpcwait', f'-rpcwaittimeout={NODE_START_TIMEOUT_SECONDS}',
                         'getblockcount')
        return self

    def __exit__(self, exception_type, exception_value, exception_traceback):
        self.bitcoin_cli('stop')
        self.bitcoind_process.wait(timeout=NODE_STOP_TIMEOUT_SECONDS)

    def _run_bitcoin_cli(self, arguments):
        bitcoin_cli_path = os.path.join(self.binary_directory, 'bitcoin-cli')
        return subprocess.run(
            [bitcoin_cli_path, '-regtest', f'-datadir={self.data_directory}',
             f'-rpcport={self.rpc_port}', *arguments],
            capture_output=True, text=True)

    def bitcoin_cli(self, *arguments):
        completed_process = self._run_bitcoin_cli(arguments)
        assert completed_process.returncode == 0, completed_process.stderr
        return completed_process.stdout.strip()

    def bitcoin_cli_json(self, *arguments):
        return json.loads(self.bitcoin_cli(*arguments))

    def bitcoin_cli_error_message(self, *arguments):
        completed_process = self._run_bitcoin_cli(arguments)
        assert completed_process.returncode != 0, completed_process.stdout
        return completed_process.stderr.strip()

    def mine_blocks(self, block_count, coinbase_address):
        self.bitcoin_cli('generatetoaddress', str(block_count), coinbase_address)


def create_miner_wallet(knots_node):
    knots_node.bitcoin_cli('-named', 'createwallet', f'wallet_name={MINER_WALLET_NAME}')


def new_miner_address(knots_node):
    return knots_node.bitcoin_cli(MINER_WALLET_ARGUMENT, 'getnewaddress')


def assert_blake2b_active(knots_node):
    blake2b_hardfork_schedule = knots_node.bitcoin_cli_json('getdeploymentinfo')['blake2b']
    assert blake2b_hardfork_schedule['active']
    assert blake2b_hardfork_schedule['height'] == BLAKE2B_ACTIVATION_HEIGHT


def account_derivation_path(account_type):
    return [account_type.purpose | HARDENED, TESTNET_COIN_TYPE, FIRST_ACCOUNT]


def descriptor_origin_path(derivation_path):
    return '/'.join(f'{child_number - HARDENED}h' for child_number in derivation_path)


def account_descriptors(jade, account_type):
    derivation_path = account_derivation_path(account_type)
    master_xpub = jade.get_xpub(XBT_REGTEST_NETWORK, [])
    account_xpub = jade.get_xpub(XBT_REGTEST_NETWORK, derivation_path)
    master_bip32_key = wally.bip32_key_from_base58(master_xpub)
    master_fingerprint = wally.bip32_key_get_fingerprint(master_bip32_key).hex()
    account_key_with_origin = (f'[{master_fingerprint}/{descriptor_origin_path(derivation_path)}]'
                               f'{account_xpub}')
    external_key = f'{account_key_with_origin}/{EXTERNAL_CHAIN}/*'
    internal_key = f'{account_key_with_origin}/{INTERNAL_CHAIN}/*'
    return (account_type.descriptor_template.format(external_key),
            account_type.descriptor_template.format(internal_key))


def descriptor_with_checksum(knots_node, descriptor):
    checksum = knots_node.bitcoin_cli_json('getdescriptorinfo', descriptor)['checksum']
    return f'{descriptor}#{checksum}'


def create_nefrita_watch_only_wallet(knots_node, jade, account_types):
    knots_node.bitcoin_cli('-named', 'createwallet', f'wallet_name={NEFRITA_WALLET_NAME}',
                           'disable_private_keys=true', 'blank=true')
    descriptor_imports = []
    for account_type in account_types:
        external_descriptor, internal_descriptor = account_descriptors(jade, account_type)
        descriptor_imports += [
            {'desc': descriptor_with_checksum(knots_node, external_descriptor), 'active': True,
             'internal': False, 'range': DESCRIPTOR_RANGE, 'timestamp': 'now'},
            {'desc': descriptor_with_checksum(knots_node, internal_descriptor), 'active': True,
             'internal': True, 'range': DESCRIPTOR_RANGE, 'timestamp': 'now'},
        ]
    import_results = knots_node.bitcoin_cli_json(NEFRITA_WALLET_ARGUMENT, 'importdescriptors',
                                                 json.dumps(descriptor_imports))
    assert all(import_result['success'] for import_result in import_results), import_results


def new_nefrita_address(knots_node, account_type):
    return knots_node.bitcoin_cli(NEFRITA_WALLET_ARGUMENT, '-named', 'getnewaddress',
                                  f'address_type={account_type.address_type}')


def finalize_psbt(knots_node, signed_psbt_bytes):
    signed_psbt_base64 = base64.b64encode(signed_psbt_bytes).decode()
    psbt_finalization = knots_node.bitcoin_cli_json('finalizepsbt', signed_psbt_base64)
    assert psbt_finalization['complete'], psbt_finalization
    return psbt_finalization['hex']


def mempool_acceptance(node, transaction_hex):
    [transaction_acceptance] = node.bitcoin_cli_json('testmempoolaccept',
                                                     json.dumps([transaction_hex]))
    return transaction_acceptance


def assert_mempool_accepts(node, transaction_hex):
    transaction_acceptance = mempool_acceptance(node, transaction_hex)
    assert transaction_acceptance['allowed'], transaction_acceptance

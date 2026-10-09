from collections import namedtuple

from . import *

pytestmark = xbt_firmware_only

HARDENED = 0x80000000
BIP84_PURPOSE = 84 | HARDENED
MAINNET_COIN_TYPE = 0 | HARDENED
TESTNET_COIN_TYPE = 1 | HARDENED
FIRST_ACCOUNT = 0 | HARDENED
EXTERNAL_CHAIN = 0
FIRST_ADDRESS_INDEX = 0

SINGLESIG_P2WPKH_VARIANT = 'wpkh(k)'
REJECTED_NETWORKS = ['mainnet', 'testnet', 'localtest', 'liquid', 'testnet-liquid',
                     'localtest-liquid']
REMOVED_SIGNING_METHODS = ['sign_tx', 'sign_liquid_tx']
PSBT_FIXTURE_FILE = 'tests/rpc/data/sign_psbt/psbt_ss_not_us.json'
BASE64_PREFIX = 'b64:'

XbtNetwork = namedtuple('XbtNetwork', ['name', 'bip32_version', 'coin_type', 'bech32_prefix'])

XBT_NETWORKS = [
    XbtNetwork('xbt', wally.BIP32_VER_MAIN_PRIVATE, MAINNET_COIN_TYPE, 'bc'),
    XbtNetwork('xbt-testnet4', wally.BIP32_VER_TEST_PRIVATE, TESTNET_COIN_TYPE, 'tb'),
    XbtNetwork('xbt-regtest', wally.BIP32_VER_TEST_PRIVATE, TESTNET_COIN_TYPE, 'bcrt'),
]
XBT_NETWORK_PARAMS = [pytest.param(network, id=network.name) for network in XBT_NETWORKS]


def _account_path(network):
    return [BIP84_PURPOSE, network.coin_type, FIRST_ACCOUNT]


def _receive_address_path(network):
    return _account_path(network) + [EXTERNAL_CHAIN, FIRST_ADDRESS_INDEX]


def _derived_key(network, path):
    seed = wally.bip39_mnemonic_to_seed512(mnemonics.default, None)
    master_key = wally.bip32_key_from_seed(seed, network.bip32_version, 0)
    return wally.bip32_key_from_parent_path(master_key, path, wally.BIP32_FLAG_KEY_PRIVATE)


def _expected_xpub(network):
    account_key = _derived_key(network, _account_path(network))
    return wally.bip32_key_to_base58(account_key, wally.BIP32_FLAG_KEY_PUBLIC)


def _expected_receive_address(network):
    address_key = _derived_key(network, _receive_address_path(network))
    return wally.bip32_key_to_addr_segwit(address_key, network.bech32_prefix, 0)


def _psbt_fixture():
    with open(PSBT_FIXTURE_FILE, 'r') as fixture_file:
        encoded_psbt = json.load(fixture_file)['input']['psbt']
    assert encoded_psbt.startswith(BASE64_PREFIX)
    return base64.b64decode(encoded_psbt[len(BASE64_PREFIX):])


def test_xbt_version_info_reports_chain(jade):
    assert jade.get_version_info()['JADE_CHAIN'] == 'XBT'


@pytest.mark.parametrize('network', XBT_NETWORK_PARAMS)
def test_xbt_network_xpub_matches_bitcoin_derivation(jade, network):
    assert jade.get_xpub(network.name, _account_path(network)) == _expected_xpub(network)


@pytest.mark.parametrize('network', XBT_NETWORK_PARAMS)
def test_xbt_network_receive_address_matches_bitcoin_derivation(jade, network):
    address = jade.get_receive_address(network.name, _receive_address_path(network),
                                       variant=SINGLESIG_P2WPKH_VARIANT)
    assert address == _expected_receive_address(network)


@pytest.mark.parametrize('network_name', REJECTED_NETWORKS)
def test_xbt_firmware_rejects_other_networks(jade, network_name):
    params = {'network': network_name, 'path': []}
    check_bad_params(jade.jade, ('other_network', 'get_xpub', params),
                     'Failed to extract valid network')


@pytest.mark.parametrize('method', REMOVED_SIGNING_METHODS)
def test_xbt_firmware_has_no_legacy_signing_flow(jade, method):
    request = jade.jade.build_request('removed_method', method, {})
    reply = jade.jade.make_rpc_call(request)
    assert reply['error']['code'] == JadeError.UNKNOWN_METHOD


def test_xbt_firmware_blocks_psbt_signing_until_unified_signing(jade):
    params = {'network': 'xbt-testnet4', 'psbt': _psbt_fixture()}
    check_bad_params(jade.jade, ('blocked_signing', 'sign_psbt', params),
                     'XBT signing is not available yet')

from . import *

pytestmark = xbt_firmware_only

LIQUID_METHOD_NAMES = ['get_master_blinding_key', 'get_blinding_key', 'get_shared_nonce',
                       'get_commitments', 'get_blinding_factor']
REGISTERED_WALLET_METHOD_NAMES = ['register_multisig', 'get_registered_multisigs',
                                  'get_registered_multisig', 'register_descriptor',
                                  'get_registered_descriptors', 'get_registered_descriptor']

GREEN_ADDRESS_FIXTURE_PATH = 'tests/rpc/data/address/greenaddress.json'
GREEN_ADDRESS_REQUEST_ID = 'green_address'
INVALID_SCRIPT_VARIANT_ERROR_MESSAGE = 'Invalid script variant parameter'

REGISTERED_WALLET_ADDRESS_REQUEST_ID = 'wallet_address'
UNSUPPORTED_REGISTERED_WALLET_ERROR_MESSAGE = 'Registered wallets are not supported'
REGISTERED_WALLET_ADDRESS_PARAMETERS = [
    pytest.param({'network': 'xbt-testnet4', 'paths': [[0, 0]], 'multisig_name': 'xbt_multisig'},
                 id='multisig_name'),
    pytest.param({'network': 'xbt-testnet4', 'branch': 0, 'pointer': 0,
                  'descriptor_name': 'xbt_descriptor'},
                 id='descriptor_name'),
]


def _green_address_parameters():
    with open(GREEN_ADDRESS_FIXTURE_PATH, 'r') as fixture_file:
        green_address_test_cases = json.load(fixture_file)
    return [pytest.param({'network': XBT_NETWORK_BY_BITCOIN_NETWORK[network],
                          'subaccount': subaccount, 'branch': branch, 'pointer': pointer,
                          'recovery_xpub': recovery_xpub, 'csv_blocks': csv_blocks},
                         id=f'{network}_subaccount_{subaccount}_pointer_{pointer}')
            for network, subaccount, branch, pointer, recovery_xpub, csv_blocks, _, _
            in green_address_test_cases if network in XBT_NETWORK_BY_BITCOIN_NETWORK]


@pytest.mark.parametrize('method_name', LIQUID_METHOD_NAMES)
def test_xbt_firmware_has_no_liquid_methods(jade, method_name):
    check_unknown_method(jade, method_name)


@pytest.mark.parametrize('method_name', REGISTERED_WALLET_METHOD_NAMES)
def test_xbt_firmware_has_no_registered_wallet_methods(jade, method_name):
    check_unknown_method(jade, method_name)


@pytest.mark.parametrize('green_address_parameters', _green_address_parameters())
def test_xbt_firmware_rejects_green_addresses(jade, green_address_parameters):
    check_bad_params(jade.jade,
                     (GREEN_ADDRESS_REQUEST_ID, 'get_receive_address', green_address_parameters),
                     INVALID_SCRIPT_VARIANT_ERROR_MESSAGE)


@pytest.mark.parametrize('registered_wallet_address_parameters',
                         REGISTERED_WALLET_ADDRESS_PARAMETERS)
def test_xbt_firmware_rejects_registered_wallet_addresses(jade,
                                                          registered_wallet_address_parameters):
    check_bad_params(jade.jade,
                     (REGISTERED_WALLET_ADDRESS_REQUEST_ID, 'get_receive_address',
                      registered_wallet_address_parameters),
                     UNSUPPORTED_REGISTERED_WALLET_ERROR_MESSAGE)

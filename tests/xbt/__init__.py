from .. import *
from ..rpc import check_bad_params

XBT_NETWORK_BY_BITCOIN_NETWORK = {
    'mainnet': 'xbt',
    'testnet': 'xbt-testnet4',
    'localtest': 'xbt-regtest',
}


def is_xbt_firmware():
    return get_jade_config().version_info.get('JADE_CHAIN') == 'XBT'


def check_unknown_method(jade, method_name):
    removed_method_request = jade.jade.build_request('removed_method', method_name, {})
    removed_method_reply = jade.jade.make_rpc_call(removed_method_request)
    assert removed_method_reply['error']['code'] == JadeError.UNKNOWN_METHOD


xbt_firmware_only = pytest.mark.skipif(not is_xbt_firmware(), reason='requires an XBT firmware')

from .. import *
from ..rpc import check_bad_params


def is_xbt_firmware():
    return get_jade_config().version_info.get('JADE_CHAIN') == 'XBT'


xbt_firmware_only = pytest.mark.skipif(not is_xbt_firmware(), reason='requires an XBT firmware')

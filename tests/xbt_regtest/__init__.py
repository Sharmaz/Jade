from .. import *
from ..xbt import is_xbt_firmware

KNOTS_BINARY_DIRECTORY = os.environ.get('KNOTS_BINARY_DIRECTORY')

xbt_knots_regtest_only = pytest.mark.skipif(
    not is_xbt_firmware() or not KNOTS_BINARY_DIRECTORY,
    reason='requires an XBT firmware and KNOTS_BINARY_DIRECTORY')

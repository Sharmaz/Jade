from . import *
from ..rpc.test_pin_actions import PINServerRecorder, pin_lifecycle

pytestmark = xbt_firmware_only

UNLOCK_NETWORK = 'xbt-regtest'
DEVELOPMENT_PINSERVER_URL = 'http://localhost:8096'
CUSTOM_PINSERVER_URL = 'https://custom-pinserver.test'
CUSTOM_PINSERVER_PUBLIC_KEY = wally.ec_public_key_from_private_key(bytes([1] * 32))


@pytest.mark.mnemonic(mnemonics.reset)
def test_xbt_firmware_creates_and_unlocks_a_pin_wallet_with_the_development_pinserver(
        pin_lifecycle):
    jade, _ = pin_lifecycle
    assert jade.set_mnemonic(mnemonics.default) is True
    development_pinserver = PINServerRecorder([DEVELOPMENT_PINSERVER_URL], certificate=None)

    assert jade.auth_user(UNLOCK_NETWORK, http_request_fn=development_pinserver.request) is True
    assert jade.logout() is True
    assert jade.auth_user(UNLOCK_NETWORK, http_request_fn=development_pinserver.request) is True

    assert development_pinserver.calls == ['set_pin', 'get_pin']


@pytest.mark.mnemonic(mnemonics.reset)
def test_xbt_pinserver_reset_restores_the_development_pinserver(pin_lifecycle):
    jade, _ = pin_lifecycle
    assert jade.set_pinserver(CUSTOM_PINSERVER_URL, pubkey=CUSTOM_PINSERVER_PUBLIC_KEY) is True
    assert jade.set_mnemonic(mnemonics.default) is True
    custom_pinserver_requests = []

    def record_request_without_answering(http_request_parameters):
        custom_pinserver_requests.append(http_request_parameters)
        return {'body': None}

    with pytest.raises(JadeError):
        jade.auth_user(UNLOCK_NETWORK, http_request_fn=record_request_without_answering)
    assert custom_pinserver_requests[0]['urls'] == [f'{CUSTOM_PINSERVER_URL}/set_pin']

    assert jade.reset_pinserver(reset_details=True, reset_certificate=True) is True
    assert jade.logout() is True
    assert jade.set_mnemonic(mnemonics.default) is True
    development_pinserver = PINServerRecorder([DEVELOPMENT_PINSERVER_URL], certificate=None)

    assert jade.auth_user(UNLOCK_NETWORK, http_request_fn=development_pinserver.request) is True
    assert development_pinserver.calls == ['set_pin']

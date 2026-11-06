from . import *

pytestmark = xbt_firmware_only


@pytest.mark.mnemonic(mnemonics.reset)
def test_xbt_firmware_reports_a_temporary_wallet_until_logout(jade, mnemonic):
    assert jade.set_mnemonic(mnemonics.default, temporary_wallet=True) is True
    version_information = jade.get_version_info()
    assert version_information['JADE_STATE'] == 'READY'
    assert version_information['NEFRITA_HAS_TEMPORARY_WALLET'] is True

    assert jade.logout() is True
    assert jade.get_version_info()['NEFRITA_HAS_TEMPORARY_WALLET'] is False


@pytest.mark.mnemonic(mnemonics.reset)
def test_xbt_firmware_reports_a_wallet_that_is_not_temporary(jade, mnemonic):
    assert jade.set_mnemonic(mnemonics.default) is True
    version_information = jade.get_version_info()
    assert version_information['JADE_STATE'] == 'READY'
    assert version_information['NEFRITA_HAS_TEMPORARY_WALLET'] is False

from collections import namedtuple

from . import *

VECTORS_FILE = 'tests/rpc/data/unified_sighash/unified_sighash.json'
VECTORS_HEADER = ['scriptCode', 'rawTx', 'inIdx', 'hashType', 'scriptType', 'spentOutputs',
                  'sighash']

SCRIPT_TYPE_BASE = 0
SCRIPT_TYPE_TAPROOT = 2
SCRIPT_TYPE_TAPSCRIPT = 3
INVALID_SCRIPT_TYPE = 4

SIGHASH_ALL = 0x01
SIGHASH_SINGLE = 0x03
SIGHASH_UNIFIED = 0x20
SIGHASH_UNDEFINED_BIT = 0x40
SIGHASH_ALL_UNIFIED = SIGHASH_ALL | SIGHASH_UNIFIED
SIGHASH_SINGLE_UNIFIED = SIGHASH_SINGLE | SIGHASH_UNIFIED
SIGHASH_ALL_UNIFIED_WITH_UNDEFINED_BIT = SIGHASH_ALL_UNIFIED | SIGHASH_UNDEFINED_BIT
SIGHASH_WIDER_THAN_A_BYTE = 0x100 | SIGHASH_ALL_UNIFIED

TAPSCRIPT_LEAF_VERSION = 0xc0
NO_CODESEPARATOR = 0xffffffff
BAD_PARAMS_REQUEST_ID = 'bad_params'

UnifiedSighashVector = namedtuple('UnifiedSighashVector', [
    'number', 'script_code', 'raw_tx', 'input_index', 'sighash', 'script_type', 'spent_outputs',
    'expected_sighash'])


def _read_vectors():
    with open(VECTORS_FILE, 'r') as json_file:
        header, *rows = json.load(json_file)
    assert header == VECTORS_HEADER
    return [UnifiedSighashVector(number, *row) for number, row in enumerate(rows, start=1)]


VECTORS = _read_vectors()


def _first_vector(predicate):
    return next(vector for vector in VECTORS if predicate(vector))


def _num_outputs(vector):
    return wally.tx_get_num_outputs(wally.tx_from_hex(vector.raw_tx, 0))


def _tapleaf_hash(tapscript):
    tapleaf = bytes([TAPSCRIPT_LEAF_VERSION]) + bytes(wally.varbuff_to_bytes(tapscript))
    return bytes(wally.bip340_tagged_hash(tapleaf, 'TapLeaf'))


def _spent_outputs(vector):
    return [{'satoshi': satoshi, 'script': bytes.fromhex(script)}
            for satoshi, script in vector.spent_outputs]


def _spent_outputs_without_script(vector):
    return [{'satoshi': satoshi} for satoshi, _ in vector.spent_outputs]


def _params(vector, **overrides):
    params = {
        'txn': bytes.fromhex(vector.raw_tx),
        'input_index': vector.input_index,
        'spent_outputs': _spent_outputs(vector),
        'script_code': bytes.fromhex(vector.script_code),
        'sighash': vector.sighash,
        'script_type': vector.script_type,
    }
    if vector.script_type == SCRIPT_TYPE_TAPSCRIPT:
        params['tapleaf_hash'] = _tapleaf_hash(bytes.fromhex(vector.script_code))
        params['codeseparator_position'] = NO_CODESEPARATOR
    params.update(overrides)
    return params


def _params_without(vector, field):
    params = _params(vector)
    del params[field]
    return params


def _get_unified_sighash(jade, params):
    return jade._jadeRpc('debug_unified_sighash', params)


@pytest.mark.parametrize('vector', [
    pytest.param(vector, id=f'vector_{vector.number:03}') for vector in VECTORS])
def test_unified_sighash_vector(jade, vector):
    assert _get_unified_sighash(jade, _params(vector)) == bytes.fromhex(vector.expected_sighash)


BASE_VECTOR = _first_vector(lambda vector: vector.script_type == SCRIPT_TYPE_BASE)
TAPROOT_VECTOR = _first_vector(lambda vector: vector.script_type == SCRIPT_TYPE_TAPROOT)
TAPSCRIPT_VECTOR = _first_vector(lambda vector: vector.script_type == SCRIPT_TYPE_TAPSCRIPT)
VECTOR_WITHOUT_OUTPUT_AT_INPUT_INDEX = _first_vector(
    lambda vector: vector.input_index >= _num_outputs(vector))

INVALID_REQUEST_CASES = [
    pytest.param(_params(BASE_VECTOR, sighash=SIGHASH_ALL),
                 'Failed to compute unified sighash',
                 id='sighash_without_unified_flag'),
    pytest.param(_params(TAPROOT_VECTOR, sighash=SIGHASH_ALL_UNIFIED_WITH_UNDEFINED_BIT),
                 'Failed to compute unified sighash',
                 id='taproot_sighash_with_undefined_bit'),
    pytest.param(_params(TAPROOT_VECTOR, sighash=SIGHASH_UNIFIED),
                 'Failed to compute unified sighash',
                 id='taproot_sighash_without_output_type'),
    pytest.param(_params(VECTOR_WITHOUT_OUTPUT_AT_INPUT_INDEX, sighash=SIGHASH_SINGLE_UNIFIED),
                 'Failed to compute unified sighash',
                 id='single_without_output_at_input_index'),
    pytest.param(_params(BASE_VECTOR, txn=bytes.fromhex('00')),
                 'Failed to extract tx',
                 id='malformed_txn'),
    pytest.param(_params(BASE_VECTOR, input_index=len(BASE_VECTOR.spent_outputs)),
                 'Failed to extract valid input index',
                 id='input_index_out_of_range'),
    pytest.param(_params(BASE_VECTOR, spent_outputs=_spent_outputs(BASE_VECTOR)[:-1]),
                 'Expecting one spent output per transaction input',
                 id='missing_spent_output'),
    pytest.param(_params(BASE_VECTOR, spent_outputs=_spent_outputs_without_script(BASE_VECTOR)),
                 'Failed to extract spent outputs',
                 id='spent_output_without_script'),
    pytest.param(_params_without(BASE_VECTOR, 'script_code'),
                 'Failed to extract script code',
                 id='missing_script_code'),
    pytest.param(_params(BASE_VECTOR, sighash=SIGHASH_WIDER_THAN_A_BYTE),
                 'Failed to extract valid sighash',
                 id='sighash_wider_than_a_byte'),
    pytest.param(_params(BASE_VECTOR, script_type=INVALID_SCRIPT_TYPE),
                 'Failed to extract valid script type',
                 id='invalid_script_type'),
    pytest.param(_params_without(TAPSCRIPT_VECTOR, 'tapleaf_hash'),
                 'Failed to extract tapleaf hash',
                 id='tapscript_without_tapleaf_hash'),
]


@pytest.mark.parametrize('params,expected_error', INVALID_REQUEST_CASES)
def test_unified_sighash_invalid_request(jade, params, expected_error):
    check_bad_params(jade.jade, (BAD_PARAMS_REQUEST_ID, 'debug_unified_sighash', params),
                     expected_error)

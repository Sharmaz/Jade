from . import *
from .unified_sighash_random_cases import NUM_RANDOM_CASES, random_case
from .unified_sighash_reference import (
    NO_CODESEPARATOR, SCRIPT_TYPE_BASE, SCRIPT_TYPE_TAPROOT, SCRIPT_TYPE_TAPSCRIPT,
    SCRIPT_TYPE_WITNESS_V0, SIGHASH_ANYONECANPAY, SIGHASH_NONE, SIGHASH_OUTPUT_TYPE_MASK,
    SIGHASH_SINGLE, SIGHASH_UNIFIED, TAPROOT_SCRIPT_TYPES, is_valid_taproot_sighash,
    serialize_transaction, unified_sighash)

BAD_PARAMS_REQUEST_ID = 'bad_params'
UNCOMPUTABLE_SIGHASH_ERROR = 'Failed to compute unified sighash'
MIN_MULTI_BYTE_COMPACT_SIZE = 0xfd
MAX_KNOTS_VECTOR_INPUTS = 3

RANDOM_CASES = [random_case(case_number) for case_number in range(NUM_RANDOM_CASES)]
RANDOM_CASE_PARAMS = [pytest.param(case, id=f'random_{case_number:03}')
                      for case_number, case in enumerate(RANDOM_CASES)]


def _expected_digest(case):
    return unified_sighash(case.transaction, case.input_index, case.spent_outputs, case.script_code,
                           case.sighash, case.script_type, case.tapleaf_hash,
                           case.codeseparator_position)


def _params(case):
    params = {
        'txn': serialize_transaction(case.transaction),
        'input_index': case.input_index,
        'spent_outputs': [{'satoshi': spent.satoshi, 'script': spent.script}
                          for spent in case.spent_outputs],
        'script_code': case.script_code,
        'sighash': case.sighash,
        'script_type': case.script_type,
    }
    if case.script_type == SCRIPT_TYPE_TAPSCRIPT:
        params['tapleaf_hash'] = case.tapleaf_hash
        params['codeseparator_position'] = case.codeseparator_position
    return params


@pytest.mark.parametrize('case', RANDOM_CASE_PARAMS)
def test_unified_sighash_matches_reference(jade, case):
    expected_digest = _expected_digest(case)
    params = _params(case)
    if expected_digest is None:
        check_bad_params(jade.jade, (BAD_PARAMS_REQUEST_ID, 'debug_unified_sighash', params),
                         UNCOMPUTABLE_SIGHASH_ERROR)
    else:
        assert jade._jadeRpc('debug_unified_sighash', params) == expected_digest


def _is_computable(case):
    return _expected_digest(case) is not None


def _output_type(case):
    return case.sighash & SIGHASH_OUTPUT_TYPE_MASK


def _has_unified_flag(case):
    return bool(case.sighash & SIGHASH_UNIFIED)


def _has_no_output_at_input_index(case):
    return case.input_index >= len(case.transaction.outputs)


def _is_long_script(script):
    return len(script) >= MIN_MULTI_BYTE_COMPACT_SIZE


COVERAGE_REQUIREMENTS = {
    'script_code_with_multi_byte_length': lambda case: (
        _is_computable(case) and case.script_type not in TAPROOT_SCRIPT_TYPES
        and _is_long_script(case.script_code)),
    'spent_script_with_multi_byte_length': lambda case: (
        _is_computable(case)
        and any(_is_long_script(spent_output.script) for spent_output in case.spent_outputs)),
    'output_script_with_multi_byte_length': lambda case: (
        _is_computable(case)
        and any(_is_long_script(tx_output.script) for tx_output in case.transaction.outputs)),
    'more_inputs_than_knots_vectors': lambda case: (
        _is_computable(case) and len(case.transaction.inputs) > MAX_KNOTS_VECTOR_INPUTS),
    'base_script_type': lambda case: (
        _is_computable(case) and case.script_type == SCRIPT_TYPE_BASE),
    'witness_v0_script_type': lambda case: (
        _is_computable(case) and case.script_type == SCRIPT_TYPE_WITNESS_V0),
    'taproot_script_type': lambda case: (
        _is_computable(case) and case.script_type == SCRIPT_TYPE_TAPROOT),
    'tapscript_with_codeseparator': lambda case: (
        _is_computable(case) and case.script_type == SCRIPT_TYPE_TAPSCRIPT
        and case.codeseparator_position != NO_CODESEPARATOR),
    'anyonecanpay': lambda case: (
        _is_computable(case) and bool(case.sighash & SIGHASH_ANYONECANPAY)),
    'none': lambda case: (
        _is_computable(case) and _output_type(case) == SIGHASH_NONE),
    'single': lambda case: (
        _is_computable(case) and _output_type(case) == SIGHASH_SINGLE),
    'rejected_without_unified_flag': lambda case: not _has_unified_flag(case),
    'rejected_taproot_sighash': lambda case: (
        _has_unified_flag(case) and case.script_type in TAPROOT_SCRIPT_TYPES
        and not is_valid_taproot_sighash(case.sighash)),
    'rejected_single_without_output': lambda case: (
        _has_unified_flag(case) and case.script_type not in TAPROOT_SCRIPT_TYPES
        and _output_type(case) == SIGHASH_SINGLE and _has_no_output_at_input_index(case)),
}


@pytest.mark.parametrize('requirement', list(COVERAGE_REQUIREMENTS))
def test_random_cases_cover_gaps_in_knots_vectors(requirement):
    assert any(COVERAGE_REQUIREMENTS[requirement](case) for case in RANDOM_CASES)

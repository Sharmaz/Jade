import random
from collections import namedtuple

from .unified_sighash_reference import (
    NO_CODESEPARATOR, SCRIPT_TYPE_BASE, SCRIPT_TYPE_TAPROOT, SCRIPT_TYPE_TAPSCRIPT,
    SCRIPT_TYPE_WITNESS_V0, SHA256_LEN, SIGHASH_ALL, SIGHASH_NONE, SIGHASH_OUTPUT_TYPE_MASK,
    SIGHASH_SINGLE, SIGHASH_UNIFIED, TAPROOT_SCRIPT_TYPES, TXID_LEN, Transaction, TxInput,
    TxOutput, serialize_transaction)

NUM_RANDOM_CASES = 200
MAX_REQUEST_LEN = 16 * 1024
REQUEST_OVERHEAD_LEN = 512
SPENT_OUTPUT_OVERHEAD_LEN = 32
MAX_MONEY = 21_000_000 * 100_000_000
MAX_SCRIPT_SIG_LEN = 30
MAX_SMALL_CODESEPARATOR_POSITION = 1000

SCRIPT_TYPES = (SCRIPT_TYPE_BASE, SCRIPT_TYPE_WITNESS_V0, SCRIPT_TYPE_TAPROOT,
                SCRIPT_TYPE_TAPSCRIPT)
VALID_TAPROOT_SIGHASHES = (0x21, 0x22, 0x23, 0xa1, 0xa2, 0xa3)
VALID_TAPROOT_SIGHASH_PROBABILITY = 0.7
NAMED_OUTPUT_TYPES = (SIGHASH_ALL, SIGHASH_NONE, SIGHASH_SINGLE)
NAMED_OUTPUT_TYPE_PROBABILITY = 0.5
UNIFIED_FLAG_PROBABILITY = 0.85

SCRIPT_LENGTH_RANGES = ((0, 0), (1, 75), (250, 260), (500, 3000))
SCRIPT_LENGTH_WEIGHTS = (10, 60, 15, 15)
COUNT_RANGES = ((1, 3), (4, 25))
COUNT_WEIGHTS = (70, 30)

UnifiedSighashCase = namedtuple('UnifiedSighashCase', [
    'transaction', 'input_index', 'spent_outputs', 'script_code', 'sighash', 'script_type',
    'tapleaf_hash', 'codeseparator_position'])


def _random_length(rng, ranges, weights):
    min_length, max_length = rng.choices(ranges, weights=weights)[0]
    return rng.randint(min_length, max_length)


def _random_script(rng):
    return rng.randbytes(_random_length(rng, SCRIPT_LENGTH_RANGES, SCRIPT_LENGTH_WEIGHTS))


def _random_input(rng):
    txid = rng.randbytes(TXID_LEN)
    vout = rng.getrandbits(32)
    script_sig = rng.randbytes(rng.randint(0, MAX_SCRIPT_SIG_LEN))
    sequence = rng.getrandbits(32)
    return TxInput(txid, vout, script_sig, sequence)


def _random_output(rng):
    satoshi = rng.randint(0, MAX_MONEY)
    return TxOutput(satoshi, _random_script(rng))


def _random_sighash(rng, script_type):
    if script_type in TAPROOT_SCRIPT_TYPES and rng.random() < VALID_TAPROOT_SIGHASH_PROBABILITY:
        return rng.choice(VALID_TAPROOT_SIGHASHES)
    sighash = rng.randrange(0x100)
    if rng.random() < NAMED_OUTPUT_TYPE_PROBABILITY:
        sighash = (sighash & ~SIGHASH_OUTPUT_TYPE_MASK) | rng.choice(NAMED_OUTPUT_TYPES)
    if rng.random() < UNIFIED_FLAG_PROBABILITY:
        sighash |= SIGHASH_UNIFIED
    return sighash


def _random_codeseparator_position(rng):
    small_position = rng.randrange(MAX_SMALL_CODESEPARATOR_POSITION)
    any_position = rng.getrandbits(32)
    return rng.choice((NO_CODESEPARATOR, small_position, any_position))


def _random_case_candidate(rng):
    num_inputs = _random_length(rng, COUNT_RANGES, COUNT_WEIGHTS)
    num_outputs = _random_length(rng, COUNT_RANGES, COUNT_WEIGHTS)
    version = rng.getrandbits(32)
    inputs = [_random_input(rng) for _ in range(num_inputs)]
    outputs = [_random_output(rng) for _ in range(num_outputs)]
    locktime = rng.getrandbits(32)
    spent_outputs = [_random_output(rng) for _ in range(num_inputs)]
    input_index = rng.randrange(num_inputs)
    script_code = _random_script(rng)
    script_type = rng.choice(SCRIPT_TYPES)
    sighash = _random_sighash(rng, script_type)
    tapleaf_hash = None
    codeseparator_position = NO_CODESEPARATOR
    if script_type == SCRIPT_TYPE_TAPSCRIPT:
        tapleaf_hash = rng.randbytes(SHA256_LEN)
        codeseparator_position = _random_codeseparator_position(rng)
    transaction = Transaction(version, inputs, outputs, locktime)
    return UnifiedSighashCase(transaction, input_index, spent_outputs, script_code, sighash,
                              script_type, tapleaf_hash, codeseparator_position)


def estimated_request_len(case):
    spent_scripts_len = sum(len(spent_output.script) for spent_output in case.spent_outputs)
    spent_outputs_overhead_len = len(case.spent_outputs) * SPENT_OUTPUT_OVERHEAD_LEN
    transaction_len = len(serialize_transaction(case.transaction))
    return (transaction_len + spent_scripts_len + spent_outputs_overhead_len
            + len(case.script_code) + REQUEST_OVERHEAD_LEN)


def random_case(case_number):
    rng = random.Random(case_number)
    while True:
        case = _random_case_candidate(rng)
        if estimated_request_len(case) <= MAX_REQUEST_LEN:
            return case

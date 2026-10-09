import hashlib
from collections import namedtuple

SIGHASH_ALL = 0x01
SIGHASH_NONE = 0x02
SIGHASH_SINGLE = 0x03
SIGHASH_UNIFIED = 0x20
SIGHASH_ANYONECANPAY = 0x80
SIGHASH_OUTPUT_TYPE_MASK = 0x1f

SCRIPT_TYPE_BASE = 0
SCRIPT_TYPE_WITNESS_V0 = 1
SCRIPT_TYPE_TAPROOT = 2
SCRIPT_TYPE_TAPSCRIPT = 3
TAPROOT_SCRIPT_TYPES = (SCRIPT_TYPE_TAPROOT, SCRIPT_TYPE_TAPSCRIPT)

UNIFIED_SIGHASH_TAG = 'UnifiedSighash'
TAPLEAF_TAG = 'TapLeaf'
TAPSCRIPT_LEAF_VERSION = 0xc0
NO_CODESEPARATOR = 0xffffffff

EPOCH = 0
LOCKTIME_EXTENSION = 0
NO_ANNEX = 0
TAPSCRIPT_KEY_VERSION = 0

SHA256_LEN = 32
TXID_LEN = 32
UINT32_LEN = 4
UINT64_LEN = 8
COMPACT_SIZE_WIDTHS = {0xfd: 2, 0xfe: 4, 0xff: 8}

TxInput = namedtuple('TxInput', ['txid', 'vout', 'script_sig', 'sequence'])
TxOutput = namedtuple('TxOutput', ['satoshi', 'script'])
Transaction = namedtuple('Transaction', ['version', 'inputs', 'outputs', 'locktime'])


def sha256(data):
    return hashlib.sha256(data).digest()


def tagged_hash(tag, message):
    tag_hash = sha256(tag.encode())
    return sha256(tag_hash + tag_hash + message)


def uint32_le(value):
    return value.to_bytes(UINT32_LEN, 'little')


def uint64_le(value):
    return value.to_bytes(UINT64_LEN, 'little')


def compact_size(value):
    if value < 0xfd:
        return bytes([value])
    if value <= 0xffff:
        return b'\xfd' + value.to_bytes(2, 'little')
    if value <= 0xffffffff:
        return b'\xfe' + value.to_bytes(4, 'little')
    return b'\xff' + value.to_bytes(8, 'little')


def length_prefixed(data):
    return compact_size(len(data)) + data


def serialize_outpoint(tx_input):
    return tx_input.txid + uint32_le(tx_input.vout)


def serialize_output(tx_output):
    return uint64_le(tx_output.satoshi) + length_prefixed(tx_output.script)


def serialize_transaction(transaction):
    serialized = uint32_le(transaction.version) + compact_size(len(transaction.inputs))
    for tx_input in transaction.inputs:
        serialized += serialize_outpoint(tx_input) + length_prefixed(tx_input.script_sig)
        serialized += uint32_le(tx_input.sequence)
    serialized += compact_size(len(transaction.outputs))
    for tx_output in transaction.outputs:
        serialized += serialize_output(tx_output)
    return serialized + uint32_le(transaction.locktime)


class SerializedReader:
    def __init__(self, data):
        self.data = data
        self.position = 0

    def read_bytes(self, length):
        chunk = self.data[self.position:self.position + length]
        assert len(chunk) == length
        self.position += length
        return chunk

    def read_uint(self, width):
        return int.from_bytes(self.read_bytes(width), 'little')

    def read_compact_size(self):
        first_byte = self.read_uint(1)
        if first_byte not in COMPACT_SIZE_WIDTHS:
            return first_byte
        return self.read_uint(COMPACT_SIZE_WIDTHS[first_byte])

    def read_length_prefixed(self):
        return self.read_bytes(self.read_compact_size())

    def is_at_end(self):
        return self.position == len(self.data)


def parse_transaction_without_witness(serialized):
    reader = SerializedReader(serialized)
    version = reader.read_uint(UINT32_LEN)
    inputs = []
    for _ in range(reader.read_compact_size()):
        txid = reader.read_bytes(TXID_LEN)
        vout = reader.read_uint(UINT32_LEN)
        script_sig = reader.read_length_prefixed()
        sequence = reader.read_uint(UINT32_LEN)
        inputs.append(TxInput(txid, vout, script_sig, sequence))
    outputs = []
    for _ in range(reader.read_compact_size()):
        satoshi = reader.read_uint(UINT64_LEN)
        script = reader.read_length_prefixed()
        outputs.append(TxOutput(satoshi, script))
    locktime = reader.read_uint(UINT32_LEN)
    assert reader.is_at_end()
    return Transaction(version, inputs, outputs, locktime)


def compute_tapleaf_hash(tapscript):
    return tagged_hash(TAPLEAF_TAG, bytes([TAPSCRIPT_LEAF_VERSION]) + length_prefixed(tapscript))


def _prevouts_hash(transaction):
    return sha256(b''.join(serialize_outpoint(tx_input) for tx_input in transaction.inputs))


def _spent_amounts_hash(spent_outputs):
    return sha256(b''.join(uint64_le(spent_output.satoshi) for spent_output in spent_outputs))


def _spent_scripts_hash(spent_outputs):
    return sha256(b''.join(length_prefixed(spent_output.script) for spent_output in spent_outputs))


def _sequences_hash(transaction):
    return sha256(b''.join(uint32_le(tx_input.sequence) for tx_input in transaction.inputs))


def _outputs_hash(transaction):
    return sha256(b''.join(serialize_output(tx_output) for tx_output in transaction.outputs))


def is_valid_taproot_sighash(sighash):
    taproot_sighash_bits = SIGHASH_OUTPUT_TYPE_MASK | SIGHASH_ANYONECANPAY | SIGHASH_UNIFIED
    output_type = sighash & SIGHASH_OUTPUT_TYPE_MASK
    has_only_taproot_sighash_bits = (sighash & ~taproot_sighash_bits) == 0
    has_defined_output_type = output_type in (SIGHASH_ALL, SIGHASH_NONE, SIGHASH_SINGLE)
    return has_only_taproot_sighash_bits and has_defined_output_type


def unified_sighash(transaction, input_index, spent_outputs, script_code, sighash, script_type,
                    tapleaf_hash=None, codeseparator_position=NO_CODESEPARATOR):
    assert 0 <= input_index < len(transaction.inputs)
    assert len(spent_outputs) == len(transaction.inputs)
    assert 0 <= sighash <= 0xff
    assert script_type != SCRIPT_TYPE_TAPSCRIPT or len(tapleaf_hash) == SHA256_LEN

    is_taproot = script_type in TAPROOT_SCRIPT_TYPES
    output_type = sighash & SIGHASH_OUTPUT_TYPE_MASK
    is_anyonecanpay = bool(sighash & SIGHASH_ANYONECANPAY)
    signs_single_output = output_type == SIGHASH_SINGLE
    signs_all_outputs = output_type not in (SIGHASH_NONE, SIGHASH_SINGLE)

    if not sighash & SIGHASH_UNIFIED:
        return None
    if is_taproot and not is_valid_taproot_sighash(sighash):
        return None
    if signs_single_output and input_index >= len(transaction.outputs):
        return None

    message = bytes([EPOCH, sighash]) + uint32_le(transaction.version)
    message += uint32_le(transaction.locktime) + bytes([LOCKTIME_EXTENSION])

    if not is_anyonecanpay:
        message += _prevouts_hash(transaction)
        message += _spent_amounts_hash(spent_outputs)
        message += _spent_scripts_hash(spent_outputs)
        message += _sequences_hash(transaction)
    if signs_all_outputs:
        message += _outputs_hash(transaction)

    message += bytes([script_type])

    if is_anyonecanpay:
        tx_input = transaction.inputs[input_index]
        message += serialize_outpoint(tx_input) + serialize_output(spent_outputs[input_index])
        message += uint32_le(tx_input.sequence)
    else:
        message += uint32_le(input_index)

    if is_taproot:
        message += bytes([NO_ANNEX])
    else:
        message += length_prefixed(script_code)

    if signs_single_output:
        message += sha256(serialize_output(transaction.outputs[input_index]))

    if script_type == SCRIPT_TYPE_TAPSCRIPT:
        message += tapleaf_hash + bytes([TAPSCRIPT_KEY_VERSION]) + uint32_le(codeseparator_position)

    return tagged_hash(UNIFIED_SIGHASH_TAG, message)

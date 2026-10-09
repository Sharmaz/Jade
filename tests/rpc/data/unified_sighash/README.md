# Unified sighash test vectors

`unified_sighash.json` is copied verbatim from Bitcoin Knots.

- Repository: https://github.com/bitcoinknots/bitcoin
- Tag: `v29.4.2.knots20260508` (commit `58398baf33e588779685ead478e6397bb28ed3d6`)
- Path in the repository: `src/test/data/unified_sighash.json`
- Git blob hash: `7f6c9685bf913cba28a334ff5b2bd1b447d44d56`
- Specification: `doc/unified-sighash.md` in the same tag (tagged hash `"UnifiedSighash"`)

The file is a JSON array. Its first entry is the header
`["scriptCode", "rawTx", "inIdx", "hashType", "scriptType", "spentOutputs", "sighash"]`,
followed by 166 test vectors.

To update it, copy the file from a newer Knots tag, check its blob hash with
`git hash-object`, and update this README.

## License

The MIT License (MIT)

Copyright (c) 2009-2025 The Bitcoin Core developers
Copyright (c) 2009-2025 Bitcoin Developers

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in
all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
THE SOFTWARE.

# Contributing

This repository is a fork of [Blockstream Jade](https://github.com/Blockstream/Jade). This guide explains how to propose changes, and how to run on your machine the same checks that run on every pull request.

## Workflow

- Branch from `master`, and open a pull request back to `master` of this repository.
- When opening the pull request on GitHub, check that the base repository is this repository and not `Blockstream/Jade`: for forks, GitHub suggests the upstream repository by default.
- Name branches with a type prefix and a short description, for example `feature/unified-sighash`, `fix/qr-scan-timeout` or `chore/add-pr-checks-workflow`.
- Write commit messages as `component: short lowercase summary`, following the existing history, for example `display: fix oob text rendering` or `tests: add tests for pin actions via debug_set_pin`.
- A pull request can be merged once every check of the `PR checks` workflow passes.

## Setup

Initialize the submodules after cloning:

```bash
git submodule update --init --recursive
```

The checks run inside the same Docker image used by CI, so Docker is the only requirement. The image is only built for `linux/amd64`; on ARM machines, such as Apple Silicon Macs, Docker runs it under emulation.

## Checks before opening a pull request

Each command block below is self-contained: copy it as a whole and paste it into a terminal opened at the repository root.

| Check | When to run it | Approximate time |
| --- | --- | --- |
| Format | Always | 1 minute |
| libjade tests | Always | 5 minutes |
| libjade tests with sanitizers | When changing C code | Longer than the plain libjade tests |
| XBT libjade tests | When changing XBT code (`CONFIG_XBT`) or the unified sighash | 5 minutes |
| XBT libjade tests with sanitizers | When changing XBT C code or the unified sighash | Longer than the XBT libjade tests |
| XBT regtest tests with Knots and Bitcoin Core | When changing XBT signing, or the Knots or Bitcoin Core version | 5 minutes plus the downloads |
| Firmware builds | When changing firmware code or board configurations | 3 minutes per board |
| XBT firmware builds | When changing XBT code or board configurations | 3 minutes per board |

### Format

```bash
JADE_BUILDER=blockstream/jade_builder@sha256:cbf0aabee7513dc8cad8f1d69a5e00f5b73bcd0965a44254627c0de4bfc8c4f2
docker run --rm --platform linux/amd64 -v "$PWD":/host/jade -w /host/jade "$JADE_BUILDER" bash -c '
  git config --global --add safe.directory /host/jade &&
  pushd /opt/esp/idf >/dev/null && . ./export.sh >/dev/null && popd >/dev/null &&
  { git grep -I "%zu" main/ libjade/; test $? -eq 1; } &&
  checksums_before_format=$(mktemp) &&
  git ls-files --cached --others --exclude-standard -z main libjade tools | xargs -0 -r sha256sum > "$checksums_before_format" &&
  ./format.sh &&
  sha256sum --quiet --check "$checksums_before_format" &&
  echo "Format check passed: format.sh changed no file"'
```

The check passes when the output ends with `Format check passed: format.sh changed no file`. It works with uncommitted changes. `format.sh` rewrites files in place: if it reformats a file, the check lists it as `FAILED` and stops, so review the change and keep it. A `%zu` format specifier, which the firmware does not support, is listed and stops the check too.

The output also includes style warnings for `main/Kconfig.projbuild` ("line should be shorter than 120 characters", "common prefix for the config names"), followed by `1 file have errors. Please take a look at the log.` They come from the upstream file: `format.sh` ignores them, and they do not fail the check.

### libjade tests

```bash
JADE_BUILDER=blockstream/jade_builder@sha256:cbf0aabee7513dc8cad8f1d69a5e00f5b73bcd0965a44254627c0de4bfc8c4f2
docker run --rm --platform linux/amd64 -v "$PWD":/host/jade -w /host/jade "$JADE_BUILDER" bash -c '
  pushd /opt/esp/idf >/dev/null && . ./export.sh >/dev/null && popd >/dev/null &&
  ./tools/switch_to.sh jade --dev --noradio &&
  pip install -q -r pinserver/requirements.txt && pip install -q . && pip install -q pytest &&
  ./libjade/make_libjade.sh Debug &&
  export LD_LIBRARY_PATH=$PWD/build_linux/libjade &&
  python ./test_jade.py --log CRITICAL --libjade &&
  pytest -v --libjade tests'
```

### libjade tests with sanitizers

```bash
JADE_BUILDER=blockstream/jade_builder@sha256:cbf0aabee7513dc8cad8f1d69a5e00f5b73bcd0965a44254627c0de4bfc8c4f2
docker run --rm --platform linux/amd64 -v "$PWD":/host/jade -w /host/jade "$JADE_BUILDER" bash -c '
  pushd /opt/esp/idf >/dev/null && . ./export.sh >/dev/null && popd >/dev/null &&
  ./tools/switch_to.sh jade --dev --noradio &&
  pip install -q -r pinserver/requirements.txt && pip install -q . && pip install -q pytest &&
  ./libjade/make_libjade.sh Sanitize -DSELFCHECK=semaphore &&
  export LD_LIBRARY_PATH=$PWD/build_linux/libjade ASAN_OPTIONS=symbolize=1,detect_leaks=0 UBSAN_OPTIONS=print_stacktrace=1 &&
  export ASAN_SO=$(gcc -print-file-name=libasan.so) &&
  LD_PRELOAD=$ASAN_SO python ./jade_cli.py --device libjade selfcheck &&
  ./libjade/make_libjade.sh Sanitize -DSELFCHECK= &&
  LD_PRELOAD=$ASAN_SO python ./test_jade.py --log CRITICAL --libjade &&
  LD_PRELOAD=$ASAN_SO pytest -v --libjade tests'
```

The first build runs the `semaphore` selfcheck (`libjade/selfcheck/semaphore.c`), which interrupts the semaphore waits of the libjade FreeRTOS emulation with signals and checks that they retry instead of aborting. CMake keeps the last `SELFCHECK` value in `build_linux`, so the second build passes `-DSELFCHECK=` to restore the default selfcheck that `test_jade.py` runs.

### XBT libjade tests

The XBT firmware is built with `CONFIG_XBT`: it only accepts the `xbt`, `xbt-testnet4` and `xbt-regtest` networks, and it never produces a signature that is valid on Bitcoin. The tests in `tests/xbt` skip themselves unless the firmware reports `"JADE_CHAIN": "XBT"` in `get_version_info`.

```bash
JADE_BUILDER=blockstream/jade_builder@sha256:cbf0aabee7513dc8cad8f1d69a5e00f5b73bcd0965a44254627c0de4bfc8c4f2
docker run --rm --platform linux/amd64 -v "$PWD":/host/jade -w /host/jade "$JADE_BUILDER" bash -c '
  pushd /opt/esp/idf >/dev/null && . ./export.sh >/dev/null && popd >/dev/null &&
  ./tools/switch_to.sh jade --dev --noradio &&
  pip install -q -r pinserver/requirements.txt && pip install -q . && pip install -q pytest &&
  export LD_LIBRARY_PATH=$PWD/build_linux/libjade &&
  ./libjade/make_libjade.sh Debug --xbt -DSELFCHECK=unified_signature &&
  python ./jade_cli.py --device libjade selfcheck &&
  ./libjade/make_libjade.sh Debug --xbt -DSELFCHECK= &&
  pytest -v --libjade tests/xbt tests/rpc/test_unified_sighash.py tests/rpc/test_unified_sighash_differential.py'
```

The first build runs the `unified_signature` selfcheck (`libjade/selfcheck/unified_signature.c`), which checks the signature verification that the XBT firmware runs after every signature. CMake keeps the last `SELFCHECK` value in `build_linux`, so the second build passes `-DSELFCHECK=` to restore the default selfcheck that `test_jade.py` runs.

### XBT libjade tests with sanitizers

The same steps as the `libjade-xbt` job of `PR checks`: the check that the Bitcoin signature hash functions banned by `main/xbt_sighash_ban.h` do not compile in an XBT build, then the `unified_signature` selfcheck and the XBT tests, with libjade built with sanitizers.

```bash
JADE_BUILDER=blockstream/jade_builder@sha256:cbf0aabee7513dc8cad8f1d69a5e00f5b73bcd0965a44254627c0de4bfc8c4f2
docker run --rm --platform linux/amd64 -v "$PWD":/host/jade -w /host/jade "$JADE_BUILDER" bash -c '
  ban_check_directory=$(mktemp -d) &&
  banned_functions=$(sed -n "s/^#pragma GCC poison //p" main/xbt_sighash_ban.h) &&
  test -n "$banned_functions" &&
  for banned_function in $banned_functions; do
    printf "#include \"xbt_sighash_ban.h\"\nvoid* banned_function_address(void) { return (void*)%s; }\n" "$banned_function" > "$ban_check_directory/check.c"
    if gcc -DCONFIG_XBT -I main -I libjade/include -I components/libwally-core/upstream/include -fsyntax-only "$ban_check_directory/check.c" 2> "$ban_check_directory/check.log"; then
      echo "$banned_function compiles in an XBT build"; exit 1
    fi
    grep -q poisoned "$ban_check_directory/check.log" || { cat "$ban_check_directory/check.log"; exit 1; }
    echo "$banned_function is banned"
  done &&
  pushd /opt/esp/idf >/dev/null && . ./export.sh >/dev/null && popd >/dev/null &&
  ./tools/switch_to.sh jade --dev --noradio &&
  pip install -q -r pinserver/requirements.txt && pip install -q . && pip install -q pytest &&
  export LD_LIBRARY_PATH=$PWD/build_linux/libjade ASAN_OPTIONS=symbolize=1,detect_leaks=0 UBSAN_OPTIONS=print_stacktrace=1 &&
  export ASAN_LIBRARY=$(gcc -print-file-name=libasan.so) &&
  ./libjade/make_libjade.sh Sanitize --xbt -DSELFCHECK=unified_signature &&
  LD_PRELOAD=$ASAN_LIBRARY python ./jade_cli.py --device libjade selfcheck &&
  ./libjade/make_libjade.sh Sanitize --xbt -DSELFCHECK= &&
  LD_PRELOAD=$ASAN_LIBRARY pytest -v --libjade tests/xbt tests/rpc/test_unified_sighash.py tests/rpc/test_unified_sighash_differential.py'
```

libjade is built with `-fno-sanitize-recover=all`, so the first memory error or undefined behavior stops the run. A failure here points to a real bug in the code, not to a flaky run.

### XBT regtest tests with Knots and Bitcoin Core

The end-to-end checks of the XBT signing, in `tests/xbt_regtest`:

- **Knots accepts the XBT signatures.** A Bitcoin Knots node in regtest, with the BLAKE2b fork active from height 200, funds a watch-only wallet built from the xpub of the XBT libjade, and creates a PSBT. libjade signs it on `xbt-regtest`, and Knots finalizes, accepts and mines it. The test also checks that the witness signature ends with the unified sighash byte (`0x21`), because Knots accepts legacy signatures too.
- **Bitcoin Core rejects them: the replay protection.** Before the fork, Knots mines a coin for each account type of the MVP (P2PKH, P2SH-P2WPKH, P2WPKH and P2TR), and those blocks are copied to a Bitcoin Core node in regtest, so the coins exist in both chains. After the fork, libjade signs a spend of each coin: Knots accepts it, and Bitcoin Core rejects it both in its mempool and in a block. The same transaction signed by the test with the Bitcoin signature hash is accepted by Bitcoin Core in both.

The tests skip themselves unless the firmware is XBT and `KNOTS_BINARY_DIRECTORY` points to the `bin` folder of Knots. The replay test also needs `BITCOIN_CORE_BINARY_DIRECTORY`, the `bin` folder of Bitcoin Core.

```bash
JADE_BUILDER=blockstream/jade_builder@sha256:cbf0aabee7513dc8cad8f1d69a5e00f5b73bcd0965a44254627c0de4bfc8c4f2
docker run --rm --platform linux/amd64 -v "$PWD":/host/jade -w /host/jade "$JADE_BUILDER" bash -c '
  knots_version=29.4.2.knots20260508 &&
  knots_tarball_name=bitcoin-$knots_version-x86_64-linux-gnu.tar.gz &&
  knots_tarball_sha256=b59d0445a317e21a03dc29425db3aba79b27d5125230b1a2b1dce62e120827c5 &&
  curl -fsSL -o /tmp/$knots_tarball_name https://bitcoinknots.org/files/29.x/$knots_version/$knots_tarball_name &&
  echo "$knots_tarball_sha256  /tmp/$knots_tarball_name" | sha256sum -c - &&
  tar -xzf /tmp/$knots_tarball_name -C /tmp &&
  bitcoin_core_version=31.1 &&
  bitcoin_core_tarball_name=bitcoin-$bitcoin_core_version-x86_64-linux-gnu.tar.gz &&
  bitcoin_core_tarball_sha256=b80d9c3e04da78fb6f0569685673418cf686fadba9042d926d13fb87ff503f9e &&
  bitcoin_core_release_url=https://bitcoincore.org/bin/bitcoin-core-$bitcoin_core_version &&
  curl -fsSL -o /tmp/$bitcoin_core_tarball_name $bitcoin_core_release_url/$bitcoin_core_tarball_name &&
  echo "$bitcoin_core_tarball_sha256  /tmp/$bitcoin_core_tarball_name" | sha256sum -c - &&
  tar -xzf /tmp/$bitcoin_core_tarball_name -C /tmp &&
  pushd /opt/esp/idf >/dev/null && . ./export.sh >/dev/null && popd >/dev/null &&
  ./tools/switch_to.sh jade --dev --noradio &&
  pip install -q -r pinserver/requirements.txt && pip install -q . && pip install -q pytest &&
  ./libjade/make_libjade.sh Debug --xbt &&
  export LD_LIBRARY_PATH=$PWD/build_linux/libjade KNOTS_BINARY_DIRECTORY=/tmp/bitcoin-$knots_version/bin &&
  export BITCOIN_CORE_BINARY_DIRECTORY=/tmp/bitcoin-$bitcoin_core_version/bin &&
  pytest -v --libjade tests/xbt_regtest'
```

The versions and the SHA256 of the Knots and Bitcoin Core tarballs are pinned here and in the `xbt-regtest` job of `PR checks`.

### Updating Knots

Repeat these steps for every new Knots release, before changing the pinned version.

1. On your machine (it needs `gpg`), verify the signatures of the release checksums in a temporary keyring, with the builder keys of the Knots Guix signature repository:

   ```bash
   knots_version=29.4.2.knots20260508
   knots_release_url=https://bitcoinknots.org/files/29.x/$knots_version
   mkdir -p ~/knots-verify/$knots_version && cd ~/knots-verify/$knots_version
   export GNUPGHOME="$PWD/gnupg"
   mkdir -p "$GNUPGHOME" && chmod 700 "$GNUPGHOME"
   curl -fsSLO "$knots_release_url/SHA256SUMS"
   curl -fsSLO "$knots_release_url/SHA256SUMS.asc"
   git clone --quiet --depth 1 --branch knots https://github.com/bitcoinknots/guix.sigs
   gpg --quiet --import guix.sigs/builder-keys/*.gpg
   gpg --verify SHA256SUMS.asc SHA256SUMS
   grep x86_64-linux-gnu.tar.gz SHA256SUMS
   ```

   `gpg --verify` must report several `Good signature` lines. The `not certified with a trusted signature` warnings are expected in a temporary keyring.

2. Compare at least two of the signing keys with a second source that does not depend on that repository: the key list of the signer's GitHub account (`https://github.com/<user>.gpg`) or `keys.openpgp.org` searched by email. The fingerprints must match; a different expiry date only means that the owner extended it.
3. Update `KNOTS_VERSION`, `KNOTS_RELEASE_URL` and `KNOTS_TARBALL_SHA256` in the `xbt-regtest` job, and the version and hash in the command block of the previous section, with the `SHA256SUMS` line of the `x86_64-linux-gnu.tar.gz` tarball.
4. If `src/test/data/unified_sighash.json` changed in the new Knots release, update `tests/rpc/data/unified_sighash/unified_sighash.json` and its pinned hash, `VECTORS_FILE_GIT_BLOB_HASH` in `tests/rpc/test_unified_sighash.py`.

### Updating Bitcoin Core

The replay test runs against a pinned Bitcoin Core release. Repeat these steps for every new release, before changing the pinned version.

1. On your machine (it needs `gpg`), verify the signatures of the release checksums in a temporary keyring, with the builder keys of the Bitcoin Core Guix signature repository:

   ```bash
   bitcoin_core_version=31.1
   bitcoin_core_release_url=https://bitcoincore.org/bin/bitcoin-core-$bitcoin_core_version
   mkdir -p ~/bitcoin-core-verify/$bitcoin_core_version && cd ~/bitcoin-core-verify/$bitcoin_core_version
   export GNUPGHOME="$PWD/gnupg"
   mkdir -p "$GNUPGHOME" && chmod 700 "$GNUPGHOME"
   curl -fsSLO "$bitcoin_core_release_url/SHA256SUMS"
   curl -fsSLO "$bitcoin_core_release_url/SHA256SUMS.asc"
   git clone --quiet --depth 1 https://github.com/bitcoin-core/guix.sigs
   gpg --quiet --import guix.sigs/builder-keys/*.gpg
   gpg --verify SHA256SUMS.asc SHA256SUMS
   grep x86_64-linux-gnu.tar.gz SHA256SUMS
   ```

   `gpg --verify` must report several `Good signature` lines. The `not certified with a trusted signature` warnings are expected in a temporary keyring.

2. Compare at least two of the signing keys with a second source, as for Knots. Some signers publish no key on their GitHub account; for them, search `keys.openpgp.org` by the email of their signature: `curl -fsSL "https://keys.openpgp.org/vks/v1/by-email/<email>" | gpg --show-keys`.
3. Update `BITCOIN_CORE_VERSION`, `BITCOIN_CORE_RELEASE_URL` and `BITCOIN_CORE_TARBALL_SHA256` in the `xbt-regtest` job, and the version and hash in the command block of the "XBT regtest tests with Knots and Bitcoin Core" section, with the `SHA256SUMS` line of the `x86_64-linux-gnu.tar.gz` tarball.
4. Run that block. If the new release words its script verification failures differently, update the expected reject reasons in `tests/xbt_regtest/test_xbt_replay.py`.

Before running the plain libjade tests again after any XBT check, rebuild libjade without `--xbt`: the rest of the suite uses the Bitcoin and Liquid networks.

### Firmware builds

Run them last: the libjade checks run `tools/switch_to.sh`, which deletes `build/`. After this check, `build/` holds the images of the last board built.

```bash
JADE_BUILDER=blockstream/jade_builder@sha256:cbf0aabee7513dc8cad8f1d69a5e00f5b73bcd0965a44254627c0de4bfc8c4f2
docker run --rm --platform linux/amd64 -v "$PWD":/host/jade -w /host/jade "$JADE_BUILDER" bash -c '
  pushd /opt/esp/idf >/dev/null && . ./export.sh >/dev/null && popd >/dev/null &&
  for board_target in display_ttgo_tdisplay:esp32 display_m5stickcplus2:esp32 display_ttgo_tdisplays3:esp32s3; do
    board=${board_target%%:*}; target=${board_target##*:}
    rm -rf sdkconfig build &&
    cp configs/sdkconfig_$board.defaults sdkconfig.defaults &&
    idf.py set-target $target && idf.py all || exit 1
  done'
```

### XBT firmware builds

An XBT firmware is the board configuration plus the `configs/sdkconfig_xbt.defaults` layer. The last check fails if the final `sdkconfig` is missing `CONFIG_XBT=y`.

```bash
JADE_BUILDER=blockstream/jade_builder@sha256:cbf0aabee7513dc8cad8f1d69a5e00f5b73bcd0965a44254627c0de4bfc8c4f2
docker run --rm --platform linux/amd64 -v "$PWD":/host/jade -w /host/jade "$JADE_BUILDER" bash -c '
  pushd /opt/esp/idf >/dev/null && . ./export.sh >/dev/null && popd >/dev/null &&
  for board_target in display_ttgo_tdisplay:esp32 display_m5stickcplus2:esp32; do
    board=${board_target%%:*}; target=${board_target##*:}
    rm -rf sdkconfig build &&
    cat configs/sdkconfig_$board.defaults configs/sdkconfig_xbt.defaults > sdkconfig.defaults &&
    idf.py set-target $target && idf.py all && grep -qx "CONFIG_XBT=y" sdkconfig || exit 1
  done'
```

## Local PIN server

A wallet with a PIN works together with a blind oracle, the PIN server: the recovery phrase is stored encrypted with a key that the device can only rebuild with the PIN and the answer of the server, and the server enforces the limit of three attempts. The device never connects to the internet: its PIN requests go through the computer it is connected to, which posts them to the server.

XBT builds use a local development server by default: `http://localhost:8096`, with no onion address, and the test key pair at the root of this repository (`server_private_key.key` and `server_public_key.pub`, the same as `pinserver/test_keys`), whose public key is `xbt_pinserver_public_key.pub`. That private key is public, so this server is only for development: an XBT build without debug mode, which is what a release build is, fails to compile until the production server replaces it.

The XBT libjade tests do not need the server: `tests/xbt/test_xbt_pinserver.py` answers the PIN requests in the same process. To unlock a board, run `pinserver/` in Docker with the test private key:

```bash
docker build --platform linux/amd64 -t local-pinserver pinserver
docker run --rm -d --name local-pinserver --platform linux/amd64 -p 8096:8096 \
  -v local-pinserver-pins:/pins \
  -v "$PWD/server_private_key.key":/server_private_key.key:ro \
  local-pinserver
```

The server is ready when `curl -s -o /dev/null -w "%{http_code}\n" http://localhost:8096/` prints `200`. `docker stop local-pinserver` stops it, and the PIN data stays in the `local-pinserver-pins` volume for the next `docker run`. jadepy posts the PIN requests of `auth_user` to the server when it is installed with the `requests` extra: `pip install '.[requests]'`.

## Continuous integration

- **`PR checks`** (`.github/workflows/pr-checks.yml`) runs on every pull request to `master`, and on demand with "Run workflow": format, firmware builds for three boards plus the XBT firmware of two of them, libjade tests, libjade tests with sanitizers, the XBT libjade tests with sanitizers, and the XBT regtest tests with Knots and Bitcoin Core. The libjade job with sanitizers also runs the `semaphore` selfcheck, and the "libjade tests with sanitizers" check runs it locally. The XBT job also checks that the Bitcoin signature hash functions banned by `main/xbt_sighash_ban.h` do not compile in an XBT build, fails if any XBT test was skipped, and runs the `unified_signature` selfcheck. The "XBT libjade tests with sanitizers" check runs the same steps locally. The `xbt-regtest` job runs the regtest tests with Knots and Bitcoin Core, with both tarballs pinned by SHA256 and cached between runs; the "XBT regtest tests with Knots and Bitcoin Core" check runs them locally. The firmware images of each board can be downloaded from the artifacts of the run, together with `flash_args`, the flash offsets that `esptool write_flash @flash_args` reads.
- `PR checks` does not run again after a merge. The `master` ruleset requires a branch to be up to date with `master` before it can be merged, so the run of the pull request already tested exactly what lands on `master`. When `master` moves while a pull request is open, update the branch ("Update branch") and wait for the checks again. To get the firmware images of `master`, run `PR checks` on `master` with "Run workflow".
- **`Scheduled checks`** (`.github/workflows/scheduled-checks.yml`) runs every Monday at 06:00 UTC and on demand: firmware builds for every DIY board, libjade selfchecks, CodeQL analysis and, on demand, a coverage report.
- The image digest (`jade_builder@sha256:…`) appears in both workflows and in every command block of this guide. When it changes, update all of them together.
- Both workflows pull the image from Docker Hub with the account in the `DOCKERHUB_USERNAME` and `DOCKERHUB_TOKEN` repository secrets, a read-only access token. Anonymous pulls hit the Docker Hub rate limit when many jobs start at once. Pull requests from forks do not receive repository secrets, so their jobs cannot pull the image yet.

## Code style

- C code is formatted with clang-format 19, using `.clang-format`.
- Python code follows pycodestyle, with a maximum line length of 100.
- `format.sh` applies both.

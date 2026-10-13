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
| XBT regtest test with Knots | When changing XBT signing or the Knots version | 5 minutes plus the Knots download |
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

### XBT regtest test with Knots

The end-to-end check of the XBT signing: a Bitcoin Knots node in regtest, with the BLAKE2b fork active from height 200, funds a watch-only wallet built from the xpub of the XBT libjade, and creates a PSBT. libjade signs it on `xbt-regtest`, and Knots finalizes, accepts and mines it. The test also checks that the witness signature ends with the unified sighash byte (`0x21`), because Knots accepts legacy signatures too. The tests in `tests/xbt_regtest` skip themselves unless the firmware is XBT and `KNOTS_BINARY_DIRECTORY` points to the `bin` folder of Knots.

```bash
JADE_BUILDER=blockstream/jade_builder@sha256:cbf0aabee7513dc8cad8f1d69a5e00f5b73bcd0965a44254627c0de4bfc8c4f2
docker run --rm --platform linux/amd64 -v "$PWD":/host/jade -w /host/jade "$JADE_BUILDER" bash -c '
  knots_version=29.4.2.knots20260508 &&
  knots_tarball_name=bitcoin-$knots_version-x86_64-linux-gnu.tar.gz &&
  knots_tarball_sha256=b59d0445a317e21a03dc29425db3aba79b27d5125230b1a2b1dce62e120827c5 &&
  curl -fsSL -o /tmp/$knots_tarball_name https://bitcoinknots.org/files/29.x/$knots_version/$knots_tarball_name &&
  echo "$knots_tarball_sha256  /tmp/$knots_tarball_name" | sha256sum -c - &&
  tar -xzf /tmp/$knots_tarball_name -C /tmp &&
  pushd /opt/esp/idf >/dev/null && . ./export.sh >/dev/null && popd >/dev/null &&
  ./tools/switch_to.sh jade --dev --noradio &&
  pip install -q -r pinserver/requirements.txt && pip install -q . && pip install -q pytest &&
  ./libjade/make_libjade.sh Debug --xbt &&
  export LD_LIBRARY_PATH=$PWD/build_linux/libjade KNOTS_BINARY_DIRECTORY=/tmp/bitcoin-$knots_version/bin &&
  pytest -v --libjade tests/xbt_regtest'
```

The version and the SHA256 of the Knots tarball are pinned here and in the `xbt-regtest` job of `PR checks`.

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

## Continuous integration

- **`PR checks`** (`.github/workflows/pr-checks.yml`) runs on every pull request to `master`, and on demand with "Run workflow": format, firmware builds for three boards plus the XBT firmware of two of them, libjade tests, libjade tests with sanitizers, the XBT libjade tests with sanitizers, and the XBT regtest test with Knots. The libjade job with sanitizers also runs the `semaphore` selfcheck, and the "libjade tests with sanitizers" check runs it locally. The XBT job also checks that the Bitcoin signature hash functions banned by `main/xbt_sighash_ban.h` do not compile in an XBT build, fails if any XBT test was skipped, and runs the `unified_signature` selfcheck. The "XBT libjade tests with sanitizers" check runs the same steps locally. The `xbt-regtest` job runs the Knots regtest test, with the Knots tarball pinned by SHA256 and cached between runs; the "XBT regtest test with Knots" check runs it locally. The firmware images of each board can be downloaded from the artifacts of the run, together with `flash_args`, the flash offsets that `esptool write_flash @flash_args` reads.
- `PR checks` does not run again after a merge. The `master` ruleset requires a branch to be up to date with `master` before it can be merged, so the run of the pull request already tested exactly what lands on `master`. When `master` moves while a pull request is open, update the branch ("Update branch") and wait for the checks again. To get the firmware images of `master`, run `PR checks` on `master` with "Run workflow".
- **`Scheduled checks`** (`.github/workflows/scheduled-checks.yml`) runs every Monday at 06:00 UTC and on demand: firmware builds for every DIY board, libjade selfchecks, CodeQL analysis and, on demand, a coverage report.
- The image digest (`jade_builder@sha256:…`) appears in both workflows and in every command block of this guide. When it changes, update all of them together.
- Both workflows pull the image from Docker Hub with the account in the `DOCKERHUB_USERNAME` and `DOCKERHUB_TOKEN` repository secrets, a read-only access token. Anonymous pulls hit the Docker Hub rate limit when many jobs start at once. Pull requests from forks do not receive repository secrets, so their jobs cannot pull the image yet.

## Code style

- C code is formatted with clang-format 19, using `.clang-format`.
- Python code follows pycodestyle, with a maximum line length of 100.
- `format.sh` applies both.

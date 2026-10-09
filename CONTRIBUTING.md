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
| Firmware builds | When changing firmware code or board configurations | 3 minutes per board |

Commit your changes before running the checks: `format.sh` rewrites files in place, so any file it changes shows up in `git status`.

### Format

```bash
JADE_BUILDER=blockstream/jade_builder@sha256:cbf0aabee7513dc8cad8f1d69a5e00f5b73bcd0965a44254627c0de4bfc8c4f2
docker run --rm --platform linux/amd64 -v "$PWD":/host/jade -w /host/jade "$JADE_BUILDER" bash -c '
  pushd /opt/esp/idf >/dev/null && . ./export.sh >/dev/null && popd >/dev/null &&
  ! git grep -I "%zu" main/ libjade/ &&
  ./format.sh'
git status --short
```

Any file listed by `git status` that you did not change was reformatted: review it and commit it.

The output includes Kconfig style warnings for `main/Kconfig.projbuild` ("line should be shorter than 120 characters", "common prefix for the config names"). They come from the upstream file and do not fail the check.

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
  ./libjade/make_libjade.sh Sanitize &&
  export LD_LIBRARY_PATH=$PWD/build_linux/libjade ASAN_OPTIONS=symbolize=1,detect_leaks=0 UBSAN_OPTIONS=print_stacktrace=1 &&
  export ASAN_SO=$(gcc -print-file-name=libasan.so) &&
  LD_PRELOAD=$ASAN_SO python ./test_jade.py --log CRITICAL --libjade &&
  LD_PRELOAD=$ASAN_SO pytest -v --libjade tests'
```

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

## Continuous integration

- **`PR checks`** (`.github/workflows/pr-checks.yml`) runs on every pull request to `master` and on every push to `master`: format, firmware builds for three boards, libjade tests, and libjade tests with sanitizers. The firmware images of each board can be downloaded from the artifacts of the run, together with `flash_args`, the flash offsets that `esptool write_flash @flash_args` reads.
- **`Scheduled checks`** (`.github/workflows/scheduled-checks.yml`) runs every Monday at 06:00 UTC and on demand: firmware builds for every DIY board, libjade selfchecks, CodeQL analysis and, on demand, a coverage report.
- The image digest (`jade_builder@sha256:…`) appears in both workflows and in every command block of this guide. When it changes, update all of them together.
- Both workflows pull the image from Docker Hub with the account in the `DOCKERHUB_USERNAME` and `DOCKERHUB_TOKEN` repository secrets, a read-only access token. Anonymous pulls hit the Docker Hub rate limit when many jobs start at once. Pull requests from forks do not receive repository secrets, so their jobs cannot pull the image yet.

## Code style

- C code is formatted with clang-format 19, using `.clang-format`.
- Python code follows pycodestyle, with a maximum line length of 100.
- `format.sh` applies both.

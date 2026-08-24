# ADR 001 — CI, the lint ruleset, and releasing to PyPI

**Status:** accepted, 2026-08-22
**Context:** ttsproof 0.3.1, four releases on PyPI, no CI, no linter config, no
type checking.

## Decision

CI is GitHub Actions, structured the same way as the sibling libraries:
`.github/workflows/ci.yml` on every push and pull request,
`.github/workflows/release.yml` on a tag, and the release **calls** `ci.yml`
through `workflow_call` rather than repeating it. Every check is a subcommand
of `scripts/ci.py`, and `python scripts/ci.py run` replays the workflow's own
steps locally, one throwaway environment per job. The general reasoning is
written up once, in `trainproof/docs/adr/001`.

Four decisions are specific to ttsproof.

### 1. macOS is in the matrix here and nowhere else

`soundfile` is a binding to **libsndfile, a C library**. The three platforms
ship it differently, and "the wheel had no usable libsndfile on macOS" is a
failure that no amount of Linux testing finds. The sibling libraries have no
compiled dependency and are tested on Linux and Windows only.

Twelve cells (3 operating systems x 4 Python versions), `fail-fast: false`.

### 2. The lint ruleset is adopted, not invented

ttsproof had no `[tool.ruff]` section at all. It now runs the same deliberate
ruleset as its siblings — `E`, `F`, `I`, `B`, `RUF013`, `S110`, with `E501`
ignored because the long lines here are output strings that tests assert.

ruff's own defaults reported **16 findings**; the chosen set reported **9**, and
all nine were fixed rather than silenced:

- seven import blocks unsorted, and `json` imported and unused in a test;
- `ONES` imported from `normalize` into `metrics` and never used;
- `zip(chunks, chunks[1:])` with no `strict=`. The fix is `strict=False`, which
  is the *correct* value and not a silencer: it is a pairwise walk, so the
  second sequence is deliberately one shorter.

**`BLE001` is deliberately not selected.** `audio.py`, `asr.py` and
`report_html.py` catch broad exceptions on purpose — they read files and drive
decoders that fail in ways this package cannot enumerate. `S110` is selected
instead: catching broadly is fine, catching and *passing* is not.

One note on the autofix, because it is the argument for reading a diff:
`ruff --fix` sorted the imports and left `src/ttsproof/__init__.py` with a
continuation block indented under the opening parenthesis at column 22. Valid
Python, correct by the linter's rules, and worse to read. Fixed by hand.

### 3. mypy runs at `python_version = "3.12"`, not at the 3.10 floor

This is forced, not chosen. numpy ships type stubs that use PEP 695 `type`
statements, and mypy under `python_version = "3.10"` refuses to parse them —
*"Type statement is only supported in Python 3.12 and greater"*, one error, no
further checking. Checking without numpy installed is worse: every numpy
expression degrades to `Any` and the report is a missing stub.

So the 3.10 floor is enforced by the test matrix, which actually runs 3.10, and
mypy checks types. `--strict` reports 58 errors here and is the ratchet, not
today's bar; the sibling `spkproof` runs strict because there it measured at
**six**, not because strictness is a house style.

### 4. Two defects the first CI run found

**A fresh clone could not run its own tests.** ttsproof is a src-layout
package: `pytest` collected all four test modules and every one died with
`ModuleNotFoundError: No module named 'ttsproof'` unless the package was
already installed. Fixed with `pythonpath = ["src"]`, and kept fixed by a
`clone` job that installs pytest and the runtime dependencies but **not** the
package. Every other job installs it first and would never notice a regression.

**`ttsproof --version` did not exist.** It exited 2 with an argparse usage
error, because a required subcommand is checked before any flag. The one
question every packaging tool and every bug report asks first had no answer,
in a published CLI, while both sibling libraries answered it. Found by the
`package` job, which installs the built wheel into a clean environment and asks
it to speak. **That change is unreleased: the source now does something 0.3.1
on PyPI does not, and it warrants 0.3.2.**

## Proving the gate stops things

A gate's output is identical whether it checked or waved something through, so
`tests/test_ci_catches_faults.py` breaks each one on purpose against a
temporary copy: a version bumped in one file only, a tag naming a version the
source does not, a stale `dist/`, a missing sdist, an attribution trailer in a
commit message, a vendor name in `pyproject.toml` — and prose naming a tool,
which must **pass**. That last one is not hypothetical here: the loose form of
the pattern failed on *"The corpus is generated with a fixed seed"* in
`src/ttsproof/cases.py`, a sentence about a random seed failing a build about
authorship.

Two of the twelve assert the third exit code rather than a failure: an
unreachable PyPI and a missing git checkout return `2`, "could not judge",
never `1`.

## Rollback

**PyPI does not allow a version to be re-uploaded.** Not after a delete, not
ever. So:

1. **Yank** the bad version — resolution stops picking it, anyone who pinned it
   can still install it, and a yank is reversible where a delete is not.
2. Fix, and ship a **patch version**. There is no path back to the number.
3. Delete only if a secret leaked, in which case rotating it is the actual fix.

`python scripts/ci.py pypi` refuses an already-published version before the
build, with that procedure in the failure text. Hard gate in `release.yml`,
advisory in `ci.yml` — between releases the current version *is* on PyPI, and a
check that is red by design gets ignored.

## One thing CI cannot fix, recorded rather than hidden

Commit `d259806` (2026-07-17) is on `origin/main` and carries an assistant
attribution trailer in its message. The attribution gate finds it and **does
not fail the build on it**: the only remedy is rewriting published history and
force-pushing, which is a decision about a public repository rather than
something a pipeline should take on its own. It is listed by SHA in
`scripts/ci.py` as `_PUBLISHED_EXEMPTIONS`, printed as a warning on every run,
and the entry disappears with the commit if the history is ever rewritten.

A gate permanently red for a reason nobody can act on inside CI is a gate
people learn to ignore. A hidden exemption is worse than a loud one.

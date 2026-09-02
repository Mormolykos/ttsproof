# Changelog

All notable changes to ttsproof are documented here. Format follows
[Keep a Changelog](https://keepachangelog.com/en/1.0.0/); versioning follows
[SemVer](https://semver.org/).

This file starts at 0.4.0. Earlier releases are described in the commit log and
in the GitHub release notes.

## [Unreleased]

Nothing yet.

## [0.4.0] — 2026-09-02 — a measurement that was never taken no longer reports zero

⚠️ **Behaviour change a consumer will notice.** Numeric fields that were never
measured are now `None` instead of `0.0`, and the CSV writes an empty cell where
it previously wrote `0.0`. Anything parsing that CSV straight into floats will
need to handle blanks.

### Fixed

- **Tail RMS and peak reported `0.0` on a clip shorter than the tail window.**
  Zero is a real, meaningful value for an audio level — it means silence — and it
  was being written for a clip the window could not be applied to at all. Every
  numeric field is now `None` until it has actually been measured.

  Under the default configuration a clip that short also trips `too_short`, so
  the misleading pair was reachable only with a custom `tail_window_sec`. Both
  paths now have tests.

### Note

This matches the pattern `ttsproof` already used for word error rate, which has
always reported blank rather than zero when ASR did not run. The audio fields
were the inconsistent ones.

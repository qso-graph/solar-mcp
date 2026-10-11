# Changelog

All notable changes to `solar-mcp` are documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.2.8] — 2026-10-11

- **ruff and mypy run in CI** (qso-graph-devel#66), as a job the `ci-all-green` gate requires.
  Settings follow `adif-mcp`, the reference for every qso-graph Python repo, rather than a style of
  this repo's own. They run once rather than per Python version: both read the source, and neither
  answer changes with the interpreter.
- NOAA's CSV-style feeds — Kp, both solar-wind files, the 27-day outlook — are rows of strings,
  not objects, and the mock stand-ins now say so. `_latest_rtsw` names what its rows hold,
  `_get_text` returns a `str` rather than `Any`, and `flare_class` admits it ends as `None` when
  nothing in NOAA's answer was readable.
- `E501` is deferred rather than adopted (qso-graph-devel#70): what it reports in these repos are
  widths, not defects, and some lines are long because they name a publisher's field exactly.
- `mcp.run` is given the literal fastmcp asks for rather than a `str` that happens to hold the
  right word.
- **`fastmcp` is bounded: `>=4.0,<5`** (qso-graph-devel#60). It was `>=3.0` with no upper bound, and
  these servers are run with `uvx`, which resolves fresh — so a `fastmcp` 5.0 would have reached
  every user automatically, before anything here had been run against it. The floor rises to 4.0
  because that is what is actually tested: every lock in the fleet held a 4.x, and nothing in CI
  has ever exercised 3.x. A claim of 3.x support that no test backs is not support.
- `fastmcp` is locked at 4.1.0, the current release, so CI runs against what a new install gets.
- **The published contact is `maintainers@qso-graph.io`** (qso-graph-devel#69). The `authors` field
  carried a personal address, and that field is what PyPI shows on the package page. Everything in
  qso-graph is open source and open to contribution, so the contact is the project's.

## [0.2.7] — 2026-10-07

- LICENSE: the full GPL-3.0 text. The file held only its opening and a link, so GitHub detected no licence.

## [0.2.6] — 2026-10-06

- PyPI: the Documentation link goes to this package's own page, https://qso-graph.io/servers/solar/ (qso-graph/.github#15).
- CI: the release flow (qso-graph/.github TEMPLATES.md). Work lands on `develop`; a release is a
  PR from `develop` into `main`, and merging it publishes to PyPI and the MCP Registry, verifies both
  and tags the release. CI runs on `develop` too, and PRs into `main` must come from `develop` or a
  `security/` branch.

## [0.2.5] — 2026-09-28

### Changed (#10)

- **No silent nulls.** When NOAA's data can't be read, `solar_conditions`, `solar_wind` and
  `solar_xray` return an error naming the feed, instead of a result full of nulls. If only some
  of a tool's feeds fail, the good values come back with a `warnings` list naming the rest.
- **SFI no longer reads 0** when the 10cm-flux feed is unreadable (the old default was `"0"`).
- **Solar wind skips gap minutes:** if the newest minute is missing data (`-9999`), it reports the
  most recent minute that has data, with that minute's timestamp.
- `__spec_version__` is now `noaa-swpc-v2`: the solar wind moved to the rtsw feeds.

### Added (CI hygiene)

- **Weekly live NOAA check** (`live-noaa.yml`): runs the live tests against NOAA SWPC every Monday.
  A failure opens a "NOAA SWPC check failing" issue, which closes when the tests pass again.

## [0.2.4] — 2026-09-28

### Fixed (NOAA SWPC 2026 format changes)

Contributed by [@AnsgarSchmidt](https://github.com/AnsgarSchmidt) ([#5](https://github.com/qso-graph/solar-mcp/pull/5)).

- **Solar wind endpoints** — `products/solar-wind/{mag,plasma}-5-minute.json`
  are gone (HTTP 404). `solar_wind()` now uses
  `json/rtsw/rtsw_mag_1m.json` and `json/rtsw/rtsw_wind_1m.json`, parsing
  `bz_gsm`/`bt` and `proton_density`/`proton_speed` keys (source is DSCOVR
  or ACE).
- **Missing-data flags** — new `_to_float()` helper treats NOAA's `-9999`
  sentinel (and JSON `null`) as `None` instead of leaking bogus values
  into `solar_wind()`/`conditions()`.
- **Trailing NUL bytes** — NOAA's file servers occasionally append `\x00`
  to JSON responses (observed on `json/goes/primary/xrays-6-hour.json`);
  `_get_json()` now strips them before parsing.
- **SFI and Kp** — the same NOAA shapes as 0.2.3, parsed through the new `_to_float()`,
  with the old shapes still accepted.
- **Newest solar wind reading** — the rtsw files are newest first, with one row per spacecraft
  per minute; `solar_wind()` takes the newest row from the active spacecraft (it was reading
  the oldest, a day old).

## [0.2.3] — 2026-09-28

### Fixed

- **solar_conditions parsing drift** — Updated `SolarClient.conditions()` (and dependent `band_outlook`) to handle current SWPC JSON shapes for `/products/summary/10cm-flux.json` (now list-of-dicts with "flux"/"time_tag") and `/products/noaa-planetary-k-index.json` (now list-of-dicts with "Kp"/"time_tag"). Added legacy fallback for old formats. Normalized scales "0" → "R0"/"S0"/"G0". Updated mocks for realism. This resolves null SFI/Kp returns and band_outlook errors. (Diagnosed via live endpoint inspection + client.py review.)

## [0.2.2] — 2026-09-28

### Added (CI hygiene)

- **MCP Registry sync** — `publish.yml` publishes to the
  [Official MCP Registry](https://registry.modelcontextprotocol.io)
  after each PyPI publish, using GitHub OIDC for auth. Triggered on
  `v*` tag push; no manual steps. Pattern documented in
  [qso-graph/.github/TEMPLATES.md](https://github.com/qso-graph/.github/blob/main/TEMPLATES.md).
  The Registry job waits until PyPI serves the version, and retries.
- **Registry version badge** in README — PyPI and Registry versions
  visible side-by-side so any drift between publishing surfaces is
  immediately apparent.
- **Release gates** — the tag must match `pyproject.toml`, and a
  `verify` job fails the release unless PyPI and the MCP Registry
  both serve the new version.

### Fixed

- The Official MCP Registry listed solar-mcp at 0.1.1 since March.
  This release brings it current.

## [0.2.1] — 2026-05-15

### Added
- New tool `get_version_info` — returns `{service_name, service_version, spec_version}`
  for fleet identity attestation. Lets agents detect version drift across MCP
  deployments without going outside the protocol. Tracks
  [IONIS-AI/ionis-devel#49](https://github.com/IONIS-AI/ionis-devel/issues/49)
  (fleet rollout).
- `__spec_version__` constant in package `__init__.py`, pinned to `noaa-swpc-v1`
  for the current NOAA SWPC endpoint set.
- L2 unit tests SOLAR-L2-041 through SOLAR-L2-045 covering the new tool.

### Changed
- `__init__.py` modernized to mirror the `adif-mcp` pattern (`Final` types,
  explicit `PackageNotFoundError` handling).

## [0.2.0] — 2026-05-14

- Standardized `pyproject.toml` metadata (email, URLs, classifiers).
- Added L2 unit tests for all 6 tools and helper functions.
- Added L3 live integration tests against NOAA SWPC endpoints.

# Changelog

All notable changes to `solar-mcp` are documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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

# Changelog

All notable changes to `solar-mcp` are documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added (CI hygiene)

- **MCP Registry sync** — `publish.yml` now publishes to the
  [Official MCP Registry](https://registry.modelcontextprotocol.io)
  after each PyPI publish, using GitHub OIDC for auth. Triggered on
  `v*` tag push; no manual steps. Pattern documented in
  [qso-graph/.github/TEMPLATES.md](https://github.com/qso-graph/.github/blob/main/TEMPLATES.md).
- **Registry version badge** in README — PyPI and Registry versions
  visible side-by-side so any drift between publishing surfaces is
  immediately apparent.

### Known drift (will resolve on next tagged release)

- Pre-`0.2.1` versions show as **stale** in the Official MCP Registry
  (last sync was at v0.1.1). Forward-only sync model: the next real
  release of solar-mcp catches the Registry up. We don't tag content-
  free releases purely to sync.

solar-mcp is the **pilot repo** for this rollout (per Patton's
2026-05-16 architecture review). Once the next solar-mcp release
demonstrates the workflow end-to-end, the same pattern fans out to
the other 12 qso-graph + IONIS-AI MCP repos.

### Fixed (NOAA SWPC 2026 format changes)

- **SFI parsing** — `products/summary/10cm-flux.json` now returns a list
  of `{"flux", "time_tag"}` dicts (was: single dict with
  `Flux`/`TimeStamp`). `conditions()` now handles both shapes.
- **Kp parsing** — `products/noaa-planetary-k-index.json` now returns dict
  rows (`{"time_tag", "Kp", ...}`) instead of list rows. `conditions()`
  now handles both shapes.
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

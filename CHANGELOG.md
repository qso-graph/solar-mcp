# Changelog

All notable changes to `solar-mcp` are documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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

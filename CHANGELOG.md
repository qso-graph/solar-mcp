# Changelog

All notable changes to `solar-mcp` are documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.5.1] — 2026-10-29

- Assert that the command is the package name
- eMudhra CA advisory: patched interpreters, pip, and a stated certifi floor

## [0.5.0] — 2026-10-27

### Added

- **A `429` from NOAA SWPC is now honoured.** NOAA SWPC asking this client to
  stop is the most explicit form a request limit takes, and it was previously
  ignored: the error was reported and the next tool call sent another request.
  Now the `Retry-After` interval is read and bounded to between a minute and an
  hour, no further call goes out until it has passed, and the tool says how long
  to wait. It does not sleep through the wait — a tool call is synchronous and an
  hour's sleep inside one is a hang, so it refuses quickly and says when to come
  back. A `503` is treated as an outage unless it carries `Retry-After`, in which
  case it is a deliberate shed and honoured the same way.


## [0.4.0] — 2026-10-26

### Changed

- **Python 3.11 is the minimum.** 3.10 reached end of life in October 2026
  ([PEP 619](https://peps.python.org/pep-0619/)), so it gets no further security
  releases on any platform. On Windows it was worse than unsupported: `uv`'s 3.10
  is built against OpenSSL 1.1.1w, end of life since September 2023, so HTTPS
  from this server ran over an unmaintained TLS library. `certifi` does not help
  with that — it supplies the root store, not the implementation.

  3.10 support was already nominal. This package has linted with
  `ruff target-version = "py311"` and type-checked with `mypy python_version =
  "3.11"` for some time, so nothing ever verified the 3.10 claim.

  `uv.lock` is regenerated and the diff is large, but **nothing is upgraded** —
  it is the 3.10 resolution branch disappearing. Packages that carried two pins,
  one per Python branch, now carry the single 3.11+ pin they already resolved to.
  An install on 3.11 or later is unchanged.

## [0.3.3] — 2026-10-26

### Changed

- `--transport streamable-http` now says where it bound, and the help text says
  it too. It binds `127.0.0.1`, and FastMCP takes no host option, so it was
  never reachable from another machine or from outside a container — and nothing
  said so. The bind address is unchanged: loopback-only is deliberate for a
  server that holds credentials and has no authentication of its own.

## [0.3.2] — 2026-10-26

### Fixed

- `--version` and `--help` now print and exit. They were ignored, so the
  command started the MCP server on stdio and waited for JSON-RPC — leaving a
  FastMCP banner on screen and an apparently hung terminal. Seven servers in
  this fleet already behaved correctly; this brings the rest in line, and a
  test asserts it.

## [0.3.1] — 2026-10-26

- **The band ratings are defined** ([BAND-OUTLOOK.md](BAND-OUTLOOK.md)). No standard defines
  band-condition words, so this one does: Excellent, Good, Fair, Poor and Sporadic, each with what
  it means on the air, and every band's rule beside them, stated as rules of thumb on SFI and Kp
  rather than a propagation model. `solar_band_outlook`'s description now names all five (it
  listed four, without Sporadic), and tests hold every rating to them and pin each band's rule at every threshold. No
  rating changed. QSO Graph Desktop's Conditions card uses the same scale.

## [0.3.0] — 2026-10-12

**Upgrading:** a tool that fails now returns `isError: true` instead of a successful result whose
payload contained an `error` key. Anything reading `result["error"]` should read the error flag.
No decision changed — a partially readable feed is still a successful answer carrying `warnings`,
and only a wholly unreadable one is an error. `conditions()` also gains `a_index`, and a non-zero
NOAA scale level now reads `G2` rather than `2`.
- **The release gate runs with the package not installed, and now says so.** `publish.yml` runs
  `tests/test_security.py` after `pip install pytest pip-audit` — deliberately, because those
  checks read the source tree rather than import it — while `ci.yml` runs the suite with
  `--ignore=tests/test_security.py`. So that file executes in exactly one environment, and it is
  the one where `import solar_mcp` raises. Two checks added with #29 imported it; every suite was
  green and the 0.3.0 publish run failed at the gate, publishing nothing. The TLS checks there are
  static again (and read code rather than prose, so a docstring explaining why `CERT_NONE` is wrong
  is not mistaken for `CERT_NONE`), the runtime assertions moved to `test_tools.py` where CI runs
  them with the package present, and `tests/test_release_gate.py` now asserts the precondition
  itself: the gate suite imports nothing but the standard library and pytest.
- **Tool execution errors are flagged `isError`** (#31). Every tool returned `{"error": "..."}` on
  failure, which reaches a client as a *successful* call whose payload happens to contain the word
  "error". The specification says why that matters: otherwise "the LLM would not be able to see that
  an error occurred and self-correct". They now raise `ToolError`, which `fastmcp` reports as
  `isError: true` with the message intact. **No decision changed — only how it is reported.** A
  partially readable feed is still a successful answer carrying `warnings`, and only a wholly
  unreadable one is an error, exactly as before.
- **Every tool declares all four annotation hints** (#31). Declaring nothing is not neutral: the
  defaults advertise a tool as `destructiveHint: true`, `openWorldHint: true` and not idempotent, and
  the specification tells clients to keep a human in the loop for operations like that — so a client
  was entitled to put a confirmation prompt in front of reading the solar flux. All seven are
  read-only, non-destructive and idempotent; `openWorldHint` is read per tool, true for the six that
  reach NOAA and false for `get_version_info`, which reports what the wheel carries. Annotations are
  a client's UX hint and never a security control; they replace no validation here.
- **A failed fetch now names what it could not reach.** Since the message is what a client now sees,
  `<urlopen error [Errno 61] Connection refused>` was not enough to tell a NOAA outage from a defect
  here. Both fetch paths raise `NOAA SWPC request failed (<url>): <reason>`.
- **Fixed: a non-zero NOAA scale level lost its letter** (#28). NOAA sends the level as a bare
  digit, and only `"0"` was being prefixed — so a quiet day reported `G0` while a **G2 storm
  reported `"2"`**. The one reading that matters was the one a caller could not identify, since
  `"2"` could as easily have been R2 or S2. Every level now carries its letter, and a prefixed
  value is kept only under its own letter: `"G2"` arriving in the R slot is not an R-scale reading
  and is not reported as one.
- **The A index is reported** (#28). `a_running` already rides along in the rows the Kp is read
  from, so it cost no request. Hams read A beside K.
- **An unusable timestamp is no longer passed through as the reading's time** (#28). NOAA has sent
  impossible dates — `2026-02-30T21:00:00` has no 30th of February — and these dated the reading
  wrongly. The reading still stands; only its time is dropped, with a warning naming what arrived
  so a format change is visible rather than silent.
- **`certifi` is carried, and every outbound call verifies against it** (#29, qso-graph-devel#73).
  Both fetches used `urllib` with no context, so they trusted whichever root store the running
  Python was built against. On macOS that is `/etc/ssl/cert.pem`, a deliberately *reduced*
  OpenSSL file — 128 roots against the system keychain's 158, and current rather than stale. A
  certificate chaining to one of the 30 it omits fails for Python while `curl` to the same URL
  succeeds, and the user is told only that the source could not be reached. That is what stopped
  `meteor-mcp` reaching NASA. **NOAA verifies fine against the reduced file today**, so this was
  latent rather than an outage: it would have surfaced the day a CA in the chain rotated.
- **Verification is never disabled.** `ssl.CERT_NONE` or `check_hostname = False` would also have
  made such a call "work", by accepting any certificate from anyone — a worse defect, and an
  invisible one. The fix is a complete root set, not a relaxed check. Three tests hold this: the
  context asserts `CERT_REQUIRED` and `check_hostname`, the roots are asserted to come from
  `certifi` and to have actually loaded, and **every `urlopen` line is required to pass the
  context**, so a new fetch path cannot quietly skip it.
- `ssl.SSLError` is handled alongside `URLError`, so a trust failure is a clean message rather
  than a traceback.
- **The recorded NOAA responses are shared with QSO Graph Desktop** (#28), in
  `tests/fixtures/noaa/`. Desktop's Conditions card follows `SolarClient`, so solar-mcp is the
  specification for its behaviour (`QGD-HOM-0008`); holding both to the same bytes is what makes
  that true rather than merely stated. The three NOAA files are byte-identical to Desktop's and
  asserted so by SHA-256, so a careless edit here is caught and the pair has to be updated
  together.
- **`tests/test_mcp_conformance.py`** asserts all of the above, so none of it can regress silently —
  seventeen checks, following `adif-mcp`'s file of the same name. `get_version_info` is the
  cautionary case: a fleet convention nobody asserted, which drifted.
- **`E501` is adopted** (#30, qso-graph-devel#70). It was deliberately ignored while the rules
  that find defects went in first; this is the pass of its own that deferral was waiting for. It
  reported **20 lines in this repo, none of them a defect**, and all but one reflowed with no name
  shortened. The exception is explicit rather than silent: one line in `client.py` carries NOAA's
  own alert text, newlines included, as the thing the parser has to read — its shape is the point,
  so it holds a `# noqa: E501` with the reason written above it. Formatting and config only; no
  behaviour changes, and the suite was unchanged by it.
- `urllib.error` is imported rather than relied on as a side effect of importing `urllib.request`.

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

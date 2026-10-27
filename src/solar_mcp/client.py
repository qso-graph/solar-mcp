"""NOAA Space Weather Prediction Center client — all public JSON endpoints."""

from __future__ import annotations

import json
import math
import os
import ssl
import threading
import time
import urllib.error
import urllib.request
from datetime import datetime
from functools import cache
from typing import Any

import certifi

from . import __version__

_SWPC = "https://services.swpc.noaa.gov"


@cache
def _context() -> ssl.SSLContext:
    """A verifying context with a current root set. Built once.

    The roots come from ``certifi`` rather than whichever store the running
    Python was built against. On macOS that distinction is real: Apple ships
    ``/etc/ssl/cert.pem`` for OpenSSL — and therefore for Python — as a
    deliberately *reduced* file, 128 roots against the system keychain's 158.
    It is current, not stale. But a certificate chaining to one of the 30 it
    omits fails for Python while ``curl`` to the same URL succeeds, and the
    user is told only that the source could not be reached (qso-graph-devel#73,
    found when meteor-mcp could not reach NASA at all).

    NOAA verifies fine against the reduced file today, so this is a latent
    defect rather than an outage: the day any CA in the chain rotates to a root
    Apple omits, this server stops working on macOS with no hint that trust is
    the cause.

    Verification is never disabled. ``ssl.CERT_NONE`` or ``check_hostname =
    False`` would also make a call "work", by accepting any certificate from
    anyone — a worse defect than this one, and an invisible one. The fix is a
    complete root set, not a relaxed check.
    """
    return ssl.create_default_context(cafile=certifi.where())


# Cache TTLs
_CONDITIONS_TTL = 900.0  # 15 minutes (SFI/Kp update slowly)
_FORECAST_TTL = 3600.0  # 1 hour
_ALERTS_TTL = 300.0  # 5 minutes
_WIND_TTL = 300.0  # 5 minutes (near-real-time DSCOVR)
_XRAY_TTL = 300.0  # 5 minutes

# Rate limiting
_MIN_DELAY = 0.2

# What to do when NOAA SWPC says stop.
#
# A 429 carrying Retry-After is the provider stating its limit outright, and it
# is the most explicit form of the stated limit guarantee 8 requires honouring.
# The interval is bounded rather than taken verbatim: a header asking for a day
# would strand an interactive tool, and one asking for nothing would let us
# hammer. See qso-graph-devel/planning/MCP-SECURITY-FRAMEWORK.md.
_MIN_BACKOFF = 60.0
_MAX_BACKOFF = 3600.0


class RateLimited(RuntimeError):
    """NOAA SWPC asked us to stop. The message is safe to show a user.

    A RuntimeError subclass so callers that already handle this client's
    failures keep working, and so FastMCP flags the tool result isError either
    way.
    """

    def __init__(self, wait: float) -> None:
        self.retry_after = max(1, round(wait))
        super().__init__(
            "NOAA SWPC is rate limiting this client; try again in "
            f"{self.retry_after} s"
        )


def _retry_after(header: str | None) -> float:
    """Seconds to wait, from a Retry-After header, clamped to our bounds.

    Retry-After may also be an HTTP date. That form is not parsed and falls back
    to the floor rather than guessing, because a wrong parse would either hammer
    NOAA SWPC or strand the user.
    """
    try:
        seconds = float(header) if header else 0.0
    except ValueError:
        seconds = 0.0
    # "nan" and "inf" parse as floats, and nan defeats the clamp below: every
    # comparison against it is False, so it would survive to be added to a
    # deadline that is then never in the future, leaving the block off
    # altogether. A header we cannot make sense of means the floor.
    if not math.isfinite(seconds):
        seconds = 0.0
    return min(max(seconds, _MIN_BACKOFF), _MAX_BACKOFF)


def _is_mock() -> bool:
    return os.getenv("SOLAR_MCP_MOCK") == "1"


def _to_float(value: Any) -> float | None:
    """Convert to float, treating NOAA missing-data flags (-9999) as None."""
    try:
        f = float(value)
    except (TypeError, ValueError):
        return None
    return None if f == -9999 else f


def _scale(letter: str, raw: Any) -> str:
    """NOAA's level for one scale, as the letter and the digit together.

    NOAA sends the level as a bare digit — ``"0"`` on a quiet day, ``"2"`` in a
    G2 storm. Only ``"0"`` was being prefixed, so a quiet day reported ``"G0"``
    and a storm reported ``"2"``: the one time the value matters it lost the
    letter saying which scale it belonged to, and a caller could not tell a G2
    from an R2 (qso-graph/solar-mcp#28).

    A value that already carries a letter is kept, but only under its own
    letter. ``"G2"`` arriving in the ``R`` slot is not an R-scale reading and
    is not reported as one.
    """
    if raw is None:
        return "unknown"
    value = str(raw).strip()
    if value.isdigit():
        return f"{letter}{value}"
    if len(value) == 2 and value[0].upper() == letter and value[1].isdigit():
        return f"{letter}{value[1]}"
    return "unknown"


def _reading_time(value: Any, label: str, warnings: list[str]) -> str | None:
    """A timestamp NOAA sent, if it is a real instant.

    NOAA has sent impossible dates — ``2026-02-30T21:00:00`` has no 30th of
    February — and these were passed through as the time of the reading, which
    dates the value wrongly rather than admitting the time is unusable. The
    value itself is still reported; only its time is dropped, and the warning
    says what arrived so a format change is visible rather than silent.
    """
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    # NOAA uses both "T" and a space, and sometimes a trailing Z. Normalised
    # here rather than per feed, because every feed has its own habit.
    probe = text.rstrip("Zz").replace(" ", "T")
    try:
        datetime.fromisoformat(probe)
    except ValueError:
        warnings.append(
            f"{label}: {text!r} is not a usable time; NOAA's format may have changed"
        )
        return None
    return text


# ---------------------------------------------------------------------------
# Mock data
# ---------------------------------------------------------------------------

_MOCK_SFI = {"timeStamp": "2026-03-04 20:00:00.000", "flux": "175", "area": ""}
_MOCK_KP: list[list[str]] = [
    ["time_tag", "Kp", "Kp_fraction", "a_running", "station_count"],
    ["2026-03-04 21:00:00.000", "3", "2.67", "15", "8"],
]
_MOCK_SCALES: dict[str, Any] = {
    "0": {
        "R": {"Scale": "R0", "Text": "none"},
        "S": {"Scale": "S0", "Text": "none"},
        "G": {"Scale": "G0", "Text": "none"},
    },
    "-1": {
        "R": {"Scale": "R1", "Text": "minor"},
        "S": {"Scale": "S0", "Text": "none"},
        "G": {"Scale": "G1", "Text": "minor"},
    },
}
_MOCK_WIND_MAG: list[list[str]] = [
    ["time_tag", "bx_gsm", "by_gsm", "bz_gsm", "bt"],
    ["2026-03-04 21:00:00.000", "-2.1", "1.5", "-3.2", "4.1"],
]
_MOCK_WIND_PLASMA: list[list[str]] = [
    ["time_tag", "density", "speed", "temperature"],
    ["2026-03-04 21:00:00.000", "5.2", "425.0", "85000"],
]
_MOCK_XRAY: list[dict[str, Any]] = [
    {"time_tag": "2026-03-04T21:00:00Z", "satellite": 16, "current_class": "B5.2",
     "current_ratio": 5.2e-7, "current_int_xrlong": 5.2e-7},
]
_MOCK_ALERTS: list[dict[str, Any]] = [
    {
        "product_id": "ALTK04",
        "issue_datetime": "2026-03-04T18:00:00Z",
        # NOAA's own alert text, reproduced exactly, newlines included: this
        # stands in for what the parser has to read, so its shape is the point.
        "message": "ALERT: Geomagnetic K-index of 4\nThreshold Reached: 2026 Mar 04 1800 UTC\nSynoptic Period: 1500-1800 UTC",  # noqa: E501
    },
]
_MOCK_FORECAST: list[list[str]] = [
    ["2026 Mar 05", "172", "3"],
    ["2026 Mar 06", "170", "2"],
    ["2026 Mar 07", "168", "2"],
]




def _check_parsed(result: dict[str, Any], feeds: list[tuple[str, str, list[str]]]) -> None:
    """Say so when NOAA's data couldn't be read, rather than returning nulls.

    ``feeds`` is (label, NOAA path, result fields) per feed. If every feed came
    back empty, raise: the tool then returns an error naming the feeds. If
    only some did, add a ``warnings`` list and keep the values that worked.
    NOAA has changed these formats without notice before, and the only symptom
    was nulls.
    """
    empty = [f"{label} ({path})" for label, path, fields in feeds
             if all(result.get(f) is None for f in fields)]
    if empty and len(empty) == len(feeds):
        raise RuntimeError(
            "NOAA SWPC returned no usable data from " + ", ".join(empty)
            + "; its format may have changed"
        )
    if empty:
        result["warnings"] = [
            f"{e}: no usable value; NOAA's format may have changed" for e in empty
        ]


def _latest_rtsw(rows: list[Any], fields: tuple[str, ...] = ()) -> Any:
    """The newest reading from NOAA's real-time solar wind feed.

    The rtsw files hold a day of 1-minute rows, newest first, with one row per
    spacecraft per minute; ``active`` marks the one NOAA is using. Take the
    newest active row, whatever order the file is in, skipping minutes where
    every one of ``fields`` is missing data (-9999 or null): a gap in the
    newest minute shouldn't hide the reading from the minute before. If no
    row has data, the newest row is returned and its values read as None.
    Legacy list-of-lists data (header row first, oldest to newest) keeps its
    last row.
    """
    dicts = [r for r in rows if isinstance(r, dict) and r.get("time_tag")]
    if not dicts:
        return rows[-1] if rows else None
    active = [r for r in dicts if r.get("active") is True] or dicts
    newest_first = sorted(active, key=lambda r: r["time_tag"], reverse=True)
    for row in newest_first:
        if not fields or any(_to_float(row.get(f)) is not None for f in fields):
            return row
    return newest_first[0]


class SolarClient:
    """NOAA SWPC client with rate limiting and caching."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._last_request: float = 0.0
        # Set by a 429: no call goes out before this. Shared by every endpoint,
        # because the limit is the provider's view of this client, not of one
        # path.
        self._blocked_until: float = 0.0
        self._cache: dict[str, tuple[float, Any]] = {}

    # ------------------------------------------------------------------
    # Cache + HTTP
    # ------------------------------------------------------------------

    def _cache_get(self, key: str) -> Any | None:
        entry = self._cache.get(key)
        if entry is None:
            return None
        expires, value = entry
        if time.monotonic() > expires:
            del self._cache[key]
            return None
        return value

    def _cache_set(self, key: str, value: Any, ttl: float) -> None:
        self._cache[key] = (time.monotonic() + ttl, value)

    def _rate_limit(self) -> None:
        """Space requests out, or refuse if NOAA has told us to stop.

        The gap between requests is slept, because that is what pacing is for. An interval
        asked for by a 429 is not: this server answers a synchronous tool call
        behind a client timeout, so sleeping out a minute or an hour inside one
        is a hang rather than restraint.

        The spacing sleep is taken *outside* the lock, and the loop re-reads
        the state after it. Without the re-read, a request that a 429 arriving
        during the sleep had just forbidden would still go out -- the check
        would have been made before the wait rather than before the request.
        """
        while True:
            with self._lock:
                now = time.monotonic()
                remaining = self._blocked_until - now
                if remaining > 0:
                    raise RateLimited(remaining)
                elapsed = now - self._last_request
                if elapsed >= _MIN_DELAY:
                    self._last_request = now
                    return
                delay = _MIN_DELAY - elapsed
            time.sleep(delay)

    def _fetch(self, url: str) -> bytes:
        """The one outbound path, so the request limits have one home.

        Both _get_json and _get_text go through here; when the 429 contract
        lived in each of them separately it was two places to keep in step.
        """
        self._rate_limit()
        req = urllib.request.Request(url, method="GET")
        req.add_header("User-Agent", f"solar-mcp/{__version__}")
        try:
            with urllib.request.urlopen(req, timeout=15, context=_context()) as resp:
                body: bytes = resp.read()
        except urllib.error.HTTPError as e:
            # 503 counts only when it carries Retry-After, which is a provider
            # shedding load deliberately; a bare 503 is an outage and falls
            # through to the named message below.
            if e.code == 429 or (e.code == 503 and e.headers.get("Retry-After")):
                # An outstanding block is never shortened: a response asking for
                # 60 s that lands while a 300 s block is still running must not
                # release us at 60. The wait raised is the one actually in force.
                asked = _retry_after(e.headers.get("Retry-After"))
                with self._lock:
                    now = time.monotonic()
                    self._blocked_until = max(self._blocked_until, now + asked)
                    wait = self._blocked_until - now
                raise RateLimited(wait) from e
            raise RuntimeError(f"NOAA SWPC request failed ({url}): {e}") from e
        except (urllib.error.URLError, ssl.SSLError) as e:
            # Named, because since #31 this message is what the client sees as
            # the tool's error. urllib's own text is "<urlopen error [Errno 61]
            # Connection refused>", which does not say what was being reached,
            # so a model reading it cannot tell a NOAA outage from a bug here.
            raise RuntimeError(f"NOAA SWPC request failed ({url}): {e}") from e
        return body

    def _get_json(self, url: str) -> Any:
        body = self._fetch(url).decode("utf-8", errors="replace")
        if not body or body.strip() == "":
            return None
        # NOAA's file servers occasionally append trailing NUL bytes
        body = body.strip("\x00").strip()
        return json.loads(body)

    # ------------------------------------------------------------------
    # Tools
    # ------------------------------------------------------------------

    def conditions(self) -> dict[str, Any]:
        """Current solar conditions: SFI, Kp, NOAA scales."""
        key = "conditions"
        cached: dict[str, Any] | None = self._cache_get(key)
        if cached is not None:
            return cached

        if _is_mock():
            sfi_data = _MOCK_SFI
            kp_data = _MOCK_KP
            scales_data = _MOCK_SCALES
        else:
            sfi_data = self._get_json(f"{_SWPC}/products/summary/10cm-flux.json") or {}
            kp_data = self._get_json(f"{_SWPC}/products/noaa-planetary-k-index.json") or []
            scales_data = self._get_json(f"{_SWPC}/products/noaa-scales.json") or {}

        # Parse SFI — NOAA returns [{"flux": 122, "time_tag": "..."}]
        sfi = None
        sfi_time = None
        if isinstance(sfi_data, list) and sfi_data:
            sfi_data = sfi_data[-1]
        if isinstance(sfi_data, dict):
            # No default: a missing value must stay None, not read as SFI 0.
            value = _to_float(sfi_data.get("Flux") or sfi_data.get("flux"))
            if value is not None and value > 0:
                sfi = int(value)
            sfi_time = (
                sfi_data.get("TimeStamp")
                or sfi_data.get("timeStamp")
                or sfi_data.get("time_tag")
            )

        # Parse latest Kp — NOAA returns dict rows {"time_tag":..., "Kp":...}.
        # The same rows carry a_running, the running A index, which hams read
        # beside K — reported here because it is already in hand (#28).
        kp = None
        kp_time = None
        a_index = None
        if isinstance(kp_data, list) and len(kp_data) > 1:
            latest = kp_data[-1]
            if isinstance(latest, dict):
                kp = _to_float(latest.get("Kp") or latest.get("kp"))
                kp_time = latest.get("time_tag") or latest.get("timeStamp")
                a_index = _to_float(latest.get("a_running"))
            elif isinstance(latest, list) and len(latest) >= 2:
                kp = _to_float(latest[1])
                kp_time = latest[0]
                # The legacy header row names the columns; a_running is the
                # fourth where it is present at all.
                if len(latest) >= 4:
                    a_index = _to_float(latest[3])

        # Parse NOAA scales (current = "0", 24hr max = "-1")
        r_scale = s_scale = g_scale = "unknown"
        if isinstance(scales_data, dict):
            current = scales_data.get("0", {})
            r_scale = _scale("R", current.get("R", {}).get("Scale"))
            s_scale = _scale("S", current.get("S", {}).get("Scale"))
            g_scale = _scale("G", current.get("G", {}).get("Scale"))

        time_warnings: list[str] = []
        result: dict[str, Any] = {
            "sfi": sfi,
            "sfi_timestamp": _reading_time(sfi_time, "SFI timestamp", time_warnings),
            "kp": kp,
            "kp_timestamp": _reading_time(kp_time, "Kp timestamp", time_warnings),
            "a_index": a_index,
            "noaa_r_scale": r_scale,
            "noaa_s_scale": s_scale,
            "noaa_g_scale": g_scale,
        }

        _check_parsed(result, [
            ("SFI", "products/summary/10cm-flux.json", ["sfi"]),
            ("Kp", "products/noaa-planetary-k-index.json", ["kp"]),
        ])
        # After _check_parsed, which assigns the list it builds. An unusable
        # time is a warning beside the value, not a reason to withhold it.
        if time_warnings:
            result.setdefault("warnings", []).extend(time_warnings)

        # Band outlook
        if sfi is not None and kp is not None:
            result["band_outlook"] = self._band_outlook(sfi, kp)

        self._cache_set(key, result, _CONDITIONS_TTL)
        return result

    def _get_text(self, url: str) -> str:
        """HTTP GET, return raw text."""
        return self._fetch(url).decode("utf-8", errors="replace")

    def forecast(self) -> dict[str, Any]:
        """27-day SFI/Kp forecast from NOAA outlook."""
        key = "forecast"
        cached: dict[str, Any] | None = self._cache_get(key)
        if cached is not None:
            return cached

        if _is_mock():
            rows = _MOCK_FORECAST
        else:
            text = self._get_text(f"{_SWPC}/text/27-day-outlook.txt")
            rows = []
            for line in text.splitlines():
                line = line.strip()
                if not line or line.startswith(("#", ":")):
                    continue
                parts = line.split()
                # Lines look like: "2026 Mar 02     150          10          3"
                if len(parts) >= 6:
                    try:
                        date_str = f"{parts[0]} {parts[1]} {parts[2]}"
                        sfi_val = parts[3]
                        kp_val = parts[5]
                        int(sfi_val)  # validate numeric
                        int(kp_val)
                        rows.append([date_str, sfi_val, kp_val])
                    except (ValueError, TypeError):
                        continue

        days = []
        for row in rows[:27]:
            try:
                days.append({
                    "date": row[0],
                    "predicted_sfi": int(row[1]),
                    "predicted_kp": int(row[2]),
                })
            except (ValueError, TypeError, IndexError):
                continue

        result = {"total_days": len(days), "forecast": days}
        self._cache_set(key, result, _FORECAST_TTL)
        return result

    def alerts(self) -> dict[str, Any]:
        """Active SWPC alerts and warnings (last 24 hours)."""
        key = "alerts"
        cached: dict[str, Any] | None = self._cache_get(key)
        if cached is not None:
            return cached

        if _is_mock():
            data = list(_MOCK_ALERTS)
        else:
            data = self._get_json(f"{_SWPC}/products/alerts.json") or []

        # Filter to last 24 hours and cap message length
        from datetime import datetime, timedelta, timezone
        cutoff = datetime.now(timezone.utc) - timedelta(hours=24)

        alerts = []
        for item in data:
            if isinstance(item, dict):
                issue_str = item.get("issue_datetime", "")
                # Parse "2026-03-06 17:53:00.083" format
                try:
                    issue_dt = datetime.strptime(
                        issue_str[:19], "%Y-%m-%d %H:%M:%S"
                    ).replace(tzinfo=timezone.utc)
                    if issue_dt < cutoff:
                        continue
                except (ValueError, TypeError):
                    pass
                msg = item.get("message", "")
                if len(msg) > 500:
                    msg = msg[:500] + "..."
                alerts.append({
                    "product_id": item.get("product_id", ""),
                    "issue_time": issue_str,
                    "message": msg,
                })

        result = {"total": len(alerts), "alerts": alerts}
        self._cache_set(key, result, _ALERTS_TTL)
        return result

    def solar_wind(self) -> dict[str, Any]:
        """Real-time DSCOVR L1 solar wind data."""
        key = "wind"
        cached: dict[str, Any] | None = self._cache_get(key)
        if cached is not None:
            return cached

        if _is_mock():
            mag_data = _MOCK_WIND_MAG
            plasma_data = _MOCK_WIND_PLASMA
        else:
            mag_data = self._get_json(f"{_SWPC}/json/rtsw/rtsw_mag_1m.json") or []
            plasma_data = self._get_json(f"{_SWPC}/json/rtsw/rtsw_wind_1m.json") or []

        # Latest magnetic field
        bz = bt = None
        mag_time = None
        if isinstance(mag_data, list) and len(mag_data) > 1:
            latest = _latest_rtsw(mag_data, ("bz_gsm", "bz_gse", "bt"))
            if isinstance(latest, dict):
                mag_time = latest.get("time_tag")
                bz = _to_float(latest.get("bz_gsm"))
                if bz is None:
                    bz = _to_float(latest.get("bz_gse"))
                bt = _to_float(latest.get("bt"))
            elif isinstance(latest, list) and len(latest) >= 4:
                mag_time = latest[0]
                bz = _to_float(latest[3])
                bt = _to_float(latest[4]) if len(latest) > 4 else None

        # Latest plasma
        speed = density = None
        plasma_time = None
        if isinstance(plasma_data, list) and len(plasma_data) > 1:
            latest = _latest_rtsw(
                plasma_data, ("proton_density", "proton_speed", "density", "speed")
            )
            if isinstance(latest, dict):
                plasma_time = latest.get("time_tag")
                density = _to_float(latest.get("proton_density") or latest.get("density"))
                speed = _to_float(latest.get("proton_speed") or latest.get("speed"))
            elif isinstance(latest, list) and len(latest) >= 3:
                plasma_time = latest[0]
                density = _to_float(latest[1])
                speed = _to_float(latest[2])

        result: dict[str, Any] = {
            "bz_gsm_nt": bz,
            "bt_nt": bt,
            "mag_timestamp": mag_time,
            "speed_km_s": speed,
            "density_p_cm3": density,
            "plasma_timestamp": plasma_time,
        }

        # Geomagnetic storm assessment
        if bz is not None:
            if bz < -10:
                result["assessment"] = "Strongly southward Bz — major storm likely"
            elif bz < -5:
                result["assessment"] = "Southward Bz — moderate storm possible"
            elif bz < 0:
                result["assessment"] = "Mildly southward Bz — minor disturbance possible"
            else:
                result["assessment"] = "Northward or neutral Bz — quiet conditions"

        _check_parsed(result, [
            ("magnetic field", "json/rtsw/rtsw_mag_1m.json", ["bz_gsm_nt", "bt_nt"]),
            ("plasma", "json/rtsw/rtsw_wind_1m.json", ["speed_km_s", "density_p_cm3"]),
        ])
        self._cache_set(key, result, _WIND_TTL)
        return result

    def xray(self) -> dict[str, Any]:
        """GOES X-ray flux and solar flare status."""
        key = "xray"
        cached: dict[str, Any] | None = self._cache_get(key)
        if cached is not None:
            return cached

        if _is_mock():
            data = _MOCK_XRAY
        else:
            data = self._get_json(f"{_SWPC}/json/goes/primary/xrays-6-hour.json") or []

        # Latest reading — NOAA now provides raw flux, not pre-classified
        flare_class: str | None = "unknown"
        xray_time = None
        flux = None
        if isinstance(data, list) and len(data) > 0:
            latest = data[-1] if isinstance(data[-1], dict) else {}
            xray_time = latest.get("time_tag")
            flux = latest.get("flux") or latest.get("current_ratio")
            # Try pre-classified first (legacy), fall back to deriving from flux
            flare_class = latest.get("current_class", "")
            if not flare_class and flux is not None:
                flare_class = self._classify_xray(flux)
        if not flare_class or flare_class == "unknown":
            flare_class = None  # nothing readable: None, so it's reported

        result: dict[str, Any] = {
            "flare_class": flare_class,
            "flux_w_m2": flux,
            "timestamp": xray_time,
        }

        # Classify
        if isinstance(flare_class, str) and len(flare_class) > 0:
            c = flare_class[0].upper()
            if c == "X":
                result["level"] = "Extreme — HF blackout likely"
            elif c == "M":
                result["level"] = "Strong — HF degradation possible"
            elif c == "C":
                result["level"] = "Moderate — minor HF impact"
            elif c == "B":
                result["level"] = "Low — no significant impact"
            elif c == "A":
                result["level"] = "Minimal — background levels"

        _check_parsed(result, [
            ("X-ray flux", "json/goes/primary/xrays-6-hour.json",
             ["flare_class", "flux_w_m2"]),
        ])
        self._cache_set(key, result, _XRAY_TTL)
        return result

    def band_outlook(self) -> dict[str, Any]:
        """HF band condition assessment derived from current indices."""
        key = "band_outlook"
        cached: dict[str, Any] | None = self._cache_get(key)
        if cached is not None:
            return cached

        # Need current SFI and Kp
        cond = self.conditions()
        sfi = cond.get("sfi")
        kp = cond.get("kp")

        if sfi is None or kp is None:
            # Raised rather than returned: the band outlook is derived from SFI
            # and Kp, so without them there is no answer to give. Returning it
            # as content would reach the client as a successful call whose
            # payload happens to say "error", which is what the specification
            # warns against — the model cannot see the failure and self-correct.
            raise RuntimeError("Unable to fetch current conditions")

        result = self._band_outlook(sfi, kp)
        result["sfi"] = sfi
        result["kp"] = kp
        self._cache_set(key, result, _CONDITIONS_TTL)
        return result

    @staticmethod
    def _classify_xray(flux: float) -> str:
        """Derive GOES flare class from X-ray flux (W/m²)."""
        if flux >= 1e-4:
            return f"X{flux / 1e-4:.1f}"
        elif flux >= 1e-5:
            return f"M{flux / 1e-5:.1f}"
        elif flux >= 1e-6:
            return f"C{flux / 1e-6:.1f}"
        elif flux >= 1e-7:
            return f"B{flux / 1e-7:.1f}"
        else:
            return f"A{flux / 1e-8:.1f}"

    @staticmethod
    def _band_outlook(sfi: int, kp: float) -> dict[str, Any]:
        """Generate band-by-band outlook from SFI and Kp."""
        storm = kp >= 5
        disturbed = kp >= 4
        active = kp >= 3

        bands = {}

        # 160m — always NVIS night, storms help (absorption kills skip)
        if storm:
            bands["160m"] = "Poor — storm absorption"
        elif active:
            bands["160m"] = "Fair — some noise"
        else:
            bands["160m"] = "Good — quiet night conditions"

        # 80m
        if storm:
            bands["80m"] = "Poor — D-layer absorption and noise"
        elif disturbed:
            bands["80m"] = "Fair — elevated absorption"
        else:
            bands["80m"] = "Good — reliable night band"

        # 40m
        if storm:
            bands["40m"] = "Fair — reduced DX"
        else:
            bands["40m"] = "Good — workhorse band, day and night"

        # 30m
        bands["30m"] = "Good — transition band, usually open"

        # 20m
        if sfi >= 150:
            bands["20m"] = "Excellent — strong F-layer, long openings"
        elif sfi >= 100:
            bands["20m"] = "Good — reliable daytime DX"
        else:
            bands["20m"] = "Fair — shorter openings at low solar flux"

        # 17m
        if sfi >= 120:
            bands["17m"] = "Good — DX openings likely"
        elif sfi >= 90:
            bands["17m"] = "Fair — marginal openings"
        else:
            bands["17m"] = "Poor — insufficient ionization"

        # 15m
        if sfi >= 140:
            bands["15m"] = "Excellent — wide open DX"
        elif sfi >= 100:
            bands["15m"] = "Good — daytime openings"
        elif sfi >= 80:
            bands["15m"] = "Fair — sporadic openings"
        else:
            bands["15m"] = "Poor — band likely closed"

        # 12m
        if sfi >= 150:
            bands["12m"] = "Good — DX openings around midday"
        elif sfi >= 120:
            bands["12m"] = "Fair — brief openings possible"
        else:
            bands["12m"] = "Poor — band likely closed"

        # 10m
        if sfi >= 160:
            bands["10m"] = "Excellent — worldwide DX"
        elif sfi >= 130:
            bands["10m"] = "Good — daytime DX openings"
        elif sfi >= 100:
            bands["10m"] = "Fair — short openings or sporadic-E"
        else:
            bands["10m"] = "Poor — closed except sporadic-E"

        # 6m
        bands["6m"] = "Sporadic — watch for Es openings"

        if storm:
            for b in ["20m", "17m", "15m", "12m", "10m"]:
                bands[b] = bands[b].split(" — ")[0] + " — degraded by geomagnetic storm"

        return {"bands": bands}

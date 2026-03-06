"""NOAA Space Weather Prediction Center client — all public JSON endpoints."""

from __future__ import annotations

import json
import os
import threading
import time
import urllib.request
from typing import Any

from . import __version__

_SWPC = "https://services.swpc.noaa.gov"

# Cache TTLs
_CONDITIONS_TTL = 900.0  # 15 minutes (SFI/Kp update slowly)
_FORECAST_TTL = 3600.0  # 1 hour
_ALERTS_TTL = 300.0  # 5 minutes
_WIND_TTL = 300.0  # 5 minutes (near-real-time DSCOVR)
_XRAY_TTL = 300.0  # 5 minutes

# Rate limiting
_MIN_DELAY = 0.2


def _is_mock() -> bool:
    return os.getenv("SOLAR_MCP_MOCK") == "1"


# ---------------------------------------------------------------------------
# Mock data
# ---------------------------------------------------------------------------

_MOCK_SFI = {"timeStamp": "2026-03-04 20:00:00.000", "flux": "175", "area": ""}
_MOCK_KP = [
    ["time_tag", "Kp", "Kp_fraction", "a_running", "station_count"],
    ["2026-03-04 21:00:00.000", "3", "2.67", "15", "8"],
]
_MOCK_SCALES = {
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
_MOCK_WIND_MAG = [
    ["time_tag", "bx_gsm", "by_gsm", "bz_gsm", "bt"],
    ["2026-03-04 21:00:00.000", "-2.1", "1.5", "-3.2", "4.1"],
]
_MOCK_WIND_PLASMA = [
    ["time_tag", "density", "speed", "temperature"],
    ["2026-03-04 21:00:00.000", "5.2", "425.0", "85000"],
]
_MOCK_XRAY = [
    {"time_tag": "2026-03-04T21:00:00Z", "satellite": 16, "current_class": "B5.2",
     "current_ratio": 5.2e-7, "current_int_xrlong": 5.2e-7},
]
_MOCK_ALERTS = [
    {
        "product_id": "ALTK04",
        "issue_datetime": "2026-03-04T18:00:00Z",
        "message": "ALERT: Geomagnetic K-index of 4\nThreshold Reached: 2026 Mar 04 1800 UTC\nSynoptic Period: 1500-1800 UTC",
    },
]
_MOCK_FORECAST = [
    ["2026 Mar 05", "172", "3"],
    ["2026 Mar 06", "170", "2"],
    ["2026 Mar 07", "168", "2"],
]


class SolarClient:
    """NOAA SWPC client with rate limiting and caching."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._last_request: float = 0.0
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
        with self._lock:
            now = time.monotonic()
            elapsed = now - self._last_request
            if elapsed < _MIN_DELAY:
                time.sleep(_MIN_DELAY - elapsed)
            self._last_request = time.monotonic()

    def _get_json(self, url: str) -> Any:
        self._rate_limit()
        req = urllib.request.Request(url, method="GET")
        req.add_header("User-Agent", f"solar-mcp/{__version__}")
        with urllib.request.urlopen(req, timeout=15) as resp:
            body = resp.read().decode("utf-8", errors="replace")
        if not body or body.strip() == "":
            return None
        return json.loads(body)

    # ------------------------------------------------------------------
    # Tools
    # ------------------------------------------------------------------

    def conditions(self) -> dict[str, Any]:
        """Current solar conditions: SFI, Kp, NOAA scales."""
        key = "conditions"
        cached = self._cache_get(key)
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

        # Parse SFI — NOAA uses capitalized keys: "Flux", "TimeStamp"
        sfi = None
        sfi_time = None
        if isinstance(sfi_data, dict):
            raw = sfi_data.get("Flux") or sfi_data.get("flux") or "0"
            try:
                sfi = int(raw)
            except (ValueError, TypeError):
                pass
            sfi_time = sfi_data.get("TimeStamp") or sfi_data.get("timeStamp")

        # Parse latest Kp
        kp = None
        kp_time = None
        if isinstance(kp_data, list) and len(kp_data) > 1:
            latest = kp_data[-1]
            if isinstance(latest, list) and len(latest) >= 2:
                try:
                    kp = float(latest[1])
                except (ValueError, TypeError):
                    pass
                kp_time = latest[0]

        # Parse NOAA scales (current = "0", 24hr max = "-1")
        r_scale = s_scale = g_scale = "unknown"
        if isinstance(scales_data, dict):
            current = scales_data.get("0", {})
            r_scale = current.get("R", {}).get("Scale", "unknown")
            s_scale = current.get("S", {}).get("Scale", "unknown")
            g_scale = current.get("G", {}).get("Scale", "unknown")

        result: dict[str, Any] = {
            "sfi": sfi,
            "sfi_timestamp": sfi_time,
            "kp": kp,
            "kp_timestamp": kp_time,
            "noaa_r_scale": r_scale,
            "noaa_s_scale": s_scale,
            "noaa_g_scale": g_scale,
        }

        # Band outlook
        if sfi is not None and kp is not None:
            result["band_outlook"] = self._band_outlook(sfi, kp)

        self._cache_set(key, result, _CONDITIONS_TTL)
        return result

    def _get_text(self, url: str) -> str:
        """HTTP GET, return raw text."""
        self._rate_limit()
        req = urllib.request.Request(url, method="GET")
        req.add_header("User-Agent", f"solar-mcp/{__version__}")
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                return resp.read().decode("utf-8", errors="replace")
        except (urllib.error.URLError, urllib.error.HTTPError):
            raise RuntimeError("NOAA SWPC request failed")

    def forecast(self) -> dict[str, Any]:
        """27-day SFI/Kp forecast from NOAA outlook."""
        key = "forecast"
        cached = self._cache_get(key)
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
        cached = self._cache_get(key)
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
        cached = self._cache_get(key)
        if cached is not None:
            return cached

        if _is_mock():
            mag_data = _MOCK_WIND_MAG
            plasma_data = _MOCK_WIND_PLASMA
        else:
            mag_data = self._get_json(f"{_SWPC}/products/solar-wind/mag-5-minute.json") or []
            plasma_data = self._get_json(f"{_SWPC}/products/solar-wind/plasma-5-minute.json") or []

        # Latest magnetic field
        bz = bt = None
        mag_time = None
        if isinstance(mag_data, list) and len(mag_data) > 1:
            latest = mag_data[-1]
            if isinstance(latest, list) and len(latest) >= 4:
                mag_time = latest[0]
                try:
                    bz = float(latest[3])
                except (ValueError, TypeError):
                    pass
                try:
                    bt = float(latest[4]) if len(latest) > 4 else None
                except (ValueError, TypeError):
                    pass

        # Latest plasma
        speed = density = None
        plasma_time = None
        if isinstance(plasma_data, list) and len(plasma_data) > 1:
            latest = plasma_data[-1]
            if isinstance(latest, list) and len(latest) >= 3:
                plasma_time = latest[0]
                try:
                    density = float(latest[1])
                except (ValueError, TypeError):
                    pass
                try:
                    speed = float(latest[2])
                except (ValueError, TypeError):
                    pass

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

        self._cache_set(key, result, _WIND_TTL)
        return result

    def xray(self) -> dict[str, Any]:
        """GOES X-ray flux and solar flare status."""
        key = "xray"
        cached = self._cache_get(key)
        if cached is not None:
            return cached

        if _is_mock():
            data = _MOCK_XRAY
        else:
            data = self._get_json(f"{_SWPC}/json/goes/primary/xrays-6-hour.json") or []

        # Latest reading — NOAA now provides raw flux, not pre-classified
        flare_class = "unknown"
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

        self._cache_set(key, result, _XRAY_TTL)
        return result

    def band_outlook(self) -> dict[str, Any]:
        """HF band condition assessment derived from current indices."""
        key = "band_outlook"
        cached = self._cache_get(key)
        if cached is not None:
            return cached

        # Need current SFI and Kp
        cond = self.conditions()
        sfi = cond.get("sfi")
        kp = cond.get("kp")

        if sfi is None or kp is None:
            return {"error": "Unable to fetch current conditions"}

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

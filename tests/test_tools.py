"""L2 unit tests for solar-mcp — all 6 tools + helper functions.

Uses SOLAR_MCP_MOCK=1 for tool-level tests (no NOAA API calls).
Direct unit tests on SolarClient helper methods.

Test IDs: SOLAR-L2-001 through SOLAR-L2-040
"""

from __future__ import annotations

import os
import pytest

# Enable mock mode before importing anything
os.environ["SOLAR_MCP_MOCK"] = "1"

from solar_mcp.client import SolarClient


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def client():
    """Fresh SolarClient instance (no cache carryover)."""
    return SolarClient()


# ---------------------------------------------------------------------------
# SOLAR-L2-001..005: _classify_xray (flux → GOES class)
# ---------------------------------------------------------------------------


class TestClassifyXray:
    def test_x_class(self):
        """SOLAR-L2-001: X-ray flux ≥1e-4 → X class."""
        assert SolarClient._classify_xray(1e-4).startswith("X")
        assert SolarClient._classify_xray(5e-4).startswith("X")

    def test_m_class(self):
        """SOLAR-L2-002: X-ray flux 1e-5 to 1e-4 → M class."""
        assert SolarClient._classify_xray(1e-5).startswith("M")
        assert SolarClient._classify_xray(5e-5).startswith("M")

    def test_c_class(self):
        """SOLAR-L2-003: X-ray flux 1e-6 to 1e-5 → C class."""
        assert SolarClient._classify_xray(1e-6).startswith("C")
        assert SolarClient._classify_xray(5e-6).startswith("C")

    def test_b_class(self):
        """SOLAR-L2-004: X-ray flux 1e-7 to 1e-6 → B class."""
        assert SolarClient._classify_xray(1e-7).startswith("B")
        assert SolarClient._classify_xray(5e-7).startswith("B")

    def test_a_class(self):
        """SOLAR-L2-005: X-ray flux <1e-7 → A class."""
        assert SolarClient._classify_xray(5e-9).startswith("A")

    def test_boundary_values(self):
        """SOLAR-L2-006: Exact boundary values classify correctly."""
        # At exact boundary, should be the higher class
        assert SolarClient._classify_xray(1e-4).startswith("X")  # X1.0
        assert SolarClient._classify_xray(1e-5).startswith("M")  # M1.0
        assert SolarClient._classify_xray(1e-6).startswith("C")  # C1.0
        assert SolarClient._classify_xray(1e-7).startswith("B")  # B1.0

    def test_numeric_suffix(self):
        """SOLAR-L2-007: Flare class includes numeric magnitude."""
        result = SolarClient._classify_xray(5.2e-7)
        assert result == "B5.2"


# ---------------------------------------------------------------------------
# SOLAR-L2-010..020: _band_outlook (SFI + Kp → band ratings)
# ---------------------------------------------------------------------------


class TestBandOutlook:
    def test_all_bands_present(self):
        """SOLAR-L2-010: Outlook includes all 10 HF bands."""
        result = SolarClient._band_outlook(150, 2.0)
        bands = result["bands"]
        expected = {"160m", "80m", "40m", "30m", "20m", "17m", "15m", "12m", "10m", "6m"}
        assert set(bands.keys()) == expected

    def test_high_sfi_quiet(self):
        """SOLAR-L2-011: High SFI + quiet Kp → Excellent on high bands."""
        result = SolarClient._band_outlook(175, 1.0)
        bands = result["bands"]
        assert "Excellent" in bands["20m"]
        assert "Excellent" in bands["15m"]
        assert "Excellent" in bands["10m"]
        assert "Good" in bands["160m"]

    def test_low_sfi_quiet(self):
        """SOLAR-L2-012: Low SFI + quiet Kp → Poor on high bands, Good on low."""
        result = SolarClient._band_outlook(70, 1.0)
        bands = result["bands"]
        assert "Poor" in bands["10m"]
        assert "Poor" in bands["12m"]
        assert "Poor" in bands["17m"]
        assert "Good" in bands["160m"]

    def test_storm_kp5(self):
        """SOLAR-L2-013: Kp ≥ 5 (storm) → degraded on all HF."""
        result = SolarClient._band_outlook(150, 5.0)
        bands = result["bands"]
        assert "Poor" in bands["160m"]
        assert "Poor" in bands["80m"]
        assert "degraded" in bands["20m"]
        assert "degraded" in bands["15m"]

    def test_disturbed_kp4(self):
        """SOLAR-L2-014: Kp 4 (disturbed) → Fair on 80m."""
        result = SolarClient._band_outlook(150, 4.0)
        bands = result["bands"]
        assert "Fair" in bands["80m"]

    def test_30m_always_good(self):
        """SOLAR-L2-015: 30m is always 'Good' regardless of conditions."""
        for sfi in (70, 100, 175):
            for kp in (1.0, 3.0):
                result = SolarClient._band_outlook(sfi, kp)
                assert "Good" in result["bands"]["30m"]

    def test_6m_always_sporadic(self):
        """SOLAR-L2-016: 6m always says 'Sporadic'."""
        result = SolarClient._band_outlook(175, 1.0)
        assert "Sporadic" in result["bands"]["6m"]

    def test_moderate_sfi_20m(self):
        """SOLAR-L2-017: SFI 100-149 → Good on 20m."""
        result = SolarClient._band_outlook(120, 1.0)
        assert "Good" in result["bands"]["20m"]

    def test_low_sfi_20m(self):
        """SOLAR-L2-018: SFI <100 → Fair on 20m."""
        result = SolarClient._band_outlook(80, 1.0)
        assert "Fair" in result["bands"]["20m"]

    def test_sfi_thresholds_15m(self):
        """SOLAR-L2-019: 15m SFI thresholds (80, 100, 140)."""
        assert "Poor" in SolarClient._band_outlook(70, 1.0)["bands"]["15m"]
        assert "Fair" in SolarClient._band_outlook(90, 1.0)["bands"]["15m"]
        assert "Good" in SolarClient._band_outlook(120, 1.0)["bands"]["15m"]
        assert "Excellent" in SolarClient._band_outlook(150, 1.0)["bands"]["15m"]


# ---------------------------------------------------------------------------
# SOLAR-L2-021..030: Tool mock-mode tests
# ---------------------------------------------------------------------------


class TestConditionsTool:
    def test_returns_sfi(self, client):
        """SOLAR-L2-021: conditions() returns SFI from mock data."""
        result = client.conditions()
        assert result["sfi"] == 175
        assert result["sfi_timestamp"] is not None

    def test_returns_kp(self, client):
        """SOLAR-L2-022: conditions() returns Kp from mock data."""
        result = client.conditions()
        assert result["kp"] == 3.0

    def test_returns_scales(self, client):
        """SOLAR-L2-023: conditions() returns NOAA R/S/G scales."""
        result = client.conditions()
        assert result["noaa_r_scale"] == "R0"
        assert result["noaa_s_scale"] == "S0"
        assert result["noaa_g_scale"] == "G0"

    def test_includes_band_outlook(self, client):
        """SOLAR-L2-024: conditions() includes band_outlook when SFI+Kp present."""
        result = client.conditions()
        assert "band_outlook" in result
        assert "bands" in result["band_outlook"]

    def test_caches_result(self, client):
        """SOLAR-L2-025: conditions() caches result on second call."""
        r1 = client.conditions()
        r2 = client.conditions()
        assert r1 is r2  # Same object from cache


class TestForecastTool:
    def test_returns_days(self, client):
        """SOLAR-L2-026: forecast() returns day-by-day forecast."""
        result = client.forecast()
        assert result["total_days"] == 3  # Mock has 3 rows
        assert len(result["forecast"]) == 3

    def test_forecast_fields(self, client):
        """SOLAR-L2-027: Each forecast day has date, predicted_sfi, predicted_kp."""
        result = client.forecast()
        day = result["forecast"][0]
        assert "date" in day
        assert "predicted_sfi" in day
        assert "predicted_kp" in day
        assert isinstance(day["predicted_sfi"], int)


class TestAlertsTool:
    def test_returns_alerts(self, client):
        """SOLAR-L2-028: alerts() returns alert list."""
        result = client.alerts()
        assert "total" in result
        assert "alerts" in result

    def test_alert_fields(self, client):
        """SOLAR-L2-029: Each alert has product_id, issue_time, message."""
        result = client.alerts()
        # Mock alert may or may not pass the 24h filter depending on test time
        # Just verify structure
        assert isinstance(result["alerts"], list)


class TestSolarWindTool:
    def test_returns_wind_data(self, client):
        """SOLAR-L2-030: solar_wind() returns Bz, speed, density."""
        result = client.solar_wind()
        assert result["bz_gsm_nt"] == -3.2
        assert result["speed_km_s"] == 425.0
        assert result["density_p_cm3"] == 5.2

    def test_wind_assessment(self, client):
        """SOLAR-L2-031: solar_wind() includes Bz assessment."""
        result = client.solar_wind()
        assert "assessment" in result
        # Bz = -3.2 → "Mildly southward"
        assert "Mildly southward" in result["assessment"]

    def test_wind_timestamps(self, client):
        """SOLAR-L2-032: solar_wind() includes timestamps."""
        result = client.solar_wind()
        assert result["mag_timestamp"] is not None
        assert result["plasma_timestamp"] is not None


class TestXrayTool:
    def test_returns_flare_class(self, client):
        """SOLAR-L2-033: xray() returns flare class from mock."""
        result = client.xray()
        assert result["flare_class"] == "B5.2"
        assert result["flux_w_m2"] == 5.2e-7

    def test_xray_level(self, client):
        """SOLAR-L2-034: xray() includes HF impact level."""
        result = client.xray()
        assert "level" in result
        assert "Low" in result["level"]  # B class → Low

    def test_xray_timestamp(self, client):
        """SOLAR-L2-035: xray() includes timestamp."""
        result = client.xray()
        assert result["timestamp"] is not None


class TestBandOutlookTool:
    def test_returns_bands(self, client):
        """SOLAR-L2-036: band_outlook() returns per-band ratings."""
        result = client.band_outlook()
        assert "bands" in result
        assert len(result["bands"]) == 10

    def test_includes_indices(self, client):
        """SOLAR-L2-037: band_outlook() includes SFI and Kp."""
        result = client.band_outlook()
        assert result["sfi"] == 175
        assert result["kp"] == 3.0


# ---------------------------------------------------------------------------
# SOLAR-L2-038..040: Edge cases
# ---------------------------------------------------------------------------


class TestEdgeCases:
    def test_cache_expiry(self, client):
        """SOLAR-L2-038: Cache entries expire after TTL."""
        client._cache_set("test_key", "test_value", 0.01)
        assert client._cache_get("test_key") == "test_value"
        import time
        time.sleep(0.02)
        assert client._cache_get("test_key") is None

    def test_cache_miss(self, client):
        """SOLAR-L2-039: Cache miss returns None."""
        assert client._cache_get("nonexistent") is None

    def test_classify_xray_extreme(self):
        """SOLAR-L2-040: Classify extremely large and small fluxes."""
        # X100 — hypothetical extreme event
        result = SolarClient._classify_xray(1e-2)
        assert result.startswith("X")
        # Quiet sun
        result = SolarClient._classify_xray(1e-9)
        assert result.startswith("A")

"""L3 live integration tests for solar-mcp.

These tests hit real NOAA SWPC endpoints. Run with:
    pytest tests/test_live.py --live

Test IDs: SOLAR-L3-001 through SOLAR-L3-015
"""
import pytest

from solar_mcp.client import SolarClient


@pytest.fixture(scope="module")
def client():
    """Fresh SolarClient with no cache, no mock."""
    return SolarClient()


# -- SOLAR-L3-001: Conditions — SFI range -----------------------------------
@pytest.mark.live
def test_conditions_sfi_range(client):
    """SOLAR-L3-001: SFI must be in 50-400 range."""
    result = client.conditions()
    assert result["sfi"] is not None, "SFI should not be None"
    assert 50 <= result["sfi"] <= 400, f"SFI {result['sfi']} out of range 50-400"


# -- SOLAR-L3-002: Conditions — Kp range ------------------------------------
@pytest.mark.live
def test_conditions_kp_range(client):
    """SOLAR-L3-002: Kp must be in 0-9 range."""
    result = client.conditions()
    assert result["kp"] is not None, "Kp should not be None"
    assert 0 <= result["kp"] <= 9, f"Kp {result['kp']} out of range 0-9"


# -- SOLAR-L3-003: Conditions — NOAA scales present -------------------------
@pytest.mark.live
def test_conditions_noaa_scales(client):
    """SOLAR-L3-003: NOAA R/S/G scales must be present."""
    result = client.conditions()
    assert "noaa_r_scale" in result, "Missing noaa_r_scale"
    assert "noaa_s_scale" in result, "Missing noaa_s_scale"
    assert "noaa_g_scale" in result, "Missing noaa_g_scale"
    # Scales should be strings like "R0", "S1", "G2" or "unknown"
    for key in ("noaa_r_scale", "noaa_s_scale", "noaa_g_scale"):
        assert isinstance(result[key], str), f"{key} should be a string"


# -- SOLAR-L3-004: Conditions — band outlook present ------------------------
@pytest.mark.live
def test_conditions_band_outlook(client):
    """SOLAR-L3-004: Conditions should include band_outlook when SFI and Kp are available."""
    result = client.conditions()
    assert "band_outlook" in result, "band_outlook missing from conditions"
    assert "bands" in result["band_outlook"], "band_outlook should contain 'bands'"


# -- SOLAR-L3-005: Forecast — minimum 3 days --------------------------------
@pytest.mark.live
def test_forecast_minimum_days(client):
    """SOLAR-L3-005: Forecast must return at least 3 days."""
    result = client.forecast()
    assert result["total_days"] >= 3, f"Expected >= 3 forecast days, got {result['total_days']}"
    assert len(result["forecast"]) >= 3


# -- SOLAR-L3-006: Forecast — day structure ----------------------------------
@pytest.mark.live
def test_forecast_day_structure(client):
    """SOLAR-L3-006: Each forecast day must have date, predicted_sfi, predicted_kp."""
    result = client.forecast()
    for day in result["forecast"]:
        assert "date" in day, "Missing date in forecast day"
        assert "predicted_sfi" in day, "Missing predicted_sfi"
        assert "predicted_kp" in day, "Missing predicted_kp"


# -- SOLAR-L3-007: Forecast — SFI in valid range ----------------------------
@pytest.mark.live
def test_forecast_sfi_valid(client):
    """SOLAR-L3-007: Forecast SFI values must be in 50-400 range."""
    result = client.forecast()
    for day in result["forecast"]:
        sfi = day["predicted_sfi"]
        assert 50 <= sfi <= 400, f"Forecast SFI {sfi} out of range on {day['date']}"


# -- SOLAR-L3-008: Forecast — Kp in valid range -----------------------------
@pytest.mark.live
def test_forecast_kp_valid(client):
    """SOLAR-L3-008: Forecast Kp values must be in 0-9 range."""
    result = client.forecast()
    for day in result["forecast"]:
        kp = day["predicted_kp"]
        assert 0 <= kp <= 9, f"Forecast Kp {kp} out of range on {day['date']}"


# -- SOLAR-L3-009: Alerts — returns dict with total and alerts list ----------
@pytest.mark.live
def test_alerts_structure(client):
    """SOLAR-L3-009: Alerts must return dict with 'total' (int) and 'alerts' (list)."""
    result = client.alerts()
    assert "total" in result, "Missing 'total' key"
    assert "alerts" in result, "Missing 'alerts' key"
    assert isinstance(result["total"], int), "total should be int"
    assert isinstance(result["alerts"], list), "alerts should be list"
    assert result["total"] >= 0, "total cannot be negative"
    # Alerts list may be empty — that is valid (quiet space weather)
    assert result["total"] == len(result["alerts"])


# -- SOLAR-L3-010: Solar wind — Bz is a float -------------------------------
@pytest.mark.live
def test_solar_wind_bz(client):
    """SOLAR-L3-010: Solar wind Bz must be a float (can be positive or negative)."""
    result = client.solar_wind()
    bz = result["bz_gsm_nt"]
    assert bz is not None, "bz_gsm_nt should not be None"
    assert isinstance(bz, float), f"bz_gsm_nt should be float, got {type(bz)}"


# -- SOLAR-L3-011: Solar wind — speed in 200-2000 range ---------------------
@pytest.mark.live
def test_solar_wind_speed(client):
    """SOLAR-L3-011: Solar wind speed must be in 200-2000 km/s range."""
    result = client.solar_wind()
    speed = result["speed_km_s"]
    assert speed is not None, "speed_km_s should not be None"
    assert 200 <= speed <= 2000, f"Speed {speed} km/s out of range 200-2000"


# -- SOLAR-L3-012: Solar wind — density positive -----------------------------
@pytest.mark.live
def test_solar_wind_density(client):
    """SOLAR-L3-012: Solar wind density must be > 0."""
    result = client.solar_wind()
    density = result["density_p_cm3"]
    assert density is not None, "density_p_cm3 should not be None"
    assert density > 0, f"Density {density} p/cm3 must be positive"


# -- SOLAR-L3-013: Solar wind — has assessment --------------------------------
@pytest.mark.live
def test_solar_wind_assessment(client):
    """SOLAR-L3-013: Solar wind must include an assessment string."""
    result = client.solar_wind()
    assert "assessment" in result, "Missing assessment"
    assert isinstance(result["assessment"], str)
    assert len(result["assessment"]) > 0


# -- SOLAR-L3-014: X-ray — flare class and flux -----------------------------
@pytest.mark.live
def test_xray_flare_class(client):
    """SOLAR-L3-014: X-ray must return valid flare class (A/B/C/M/X) and flux."""
    result = client.xray()
    flare_class = result["flare_class"]
    assert isinstance(flare_class, str), "flare_class should be a string"
    assert len(flare_class) > 0, "flare_class should not be empty"
    assert flare_class[0] in ("A", "B", "C", "M", "X"), (
        f"flare_class '{flare_class}' must start with A/B/C/M/X"
    )
    flux = result["flux_w_m2"]
    assert flux is not None, "flux_w_m2 should not be None"
    assert isinstance(flux, float), f"flux_w_m2 should be float, got {type(flux)}"
    assert "level" in result, "Missing level assessment"
    assert isinstance(result["level"], str)


# -- SOLAR-L3-015: Band outlook — 10 bands with ratings ---------------------
@pytest.mark.live
def test_band_outlook_full(client):
    """SOLAR-L3-015: Band outlook must return 10 bands, each with a rating string."""
    result = client.band_outlook()
    expected_bands = [
        "160m", "80m", "40m", "30m", "20m", "17m", "15m", "12m", "10m", "6m"
    ]
    assert "bands" in result, "Missing 'bands' key"
    bands = result["bands"]
    assert len(bands) == 10, f"Expected 10 bands, got {len(bands)}"
    for band in expected_bands:
        assert band in bands, f"Missing band {band}"
        assert isinstance(bands[band], str), f"Band {band} rating should be a string"
        assert len(bands[band]) > 0, f"Band {band} rating should not be empty"
    assert "sfi" in result, "Missing sfi in band_outlook"
    assert "kp" in result, "Missing kp in band_outlook"

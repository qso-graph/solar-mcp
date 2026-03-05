"""solar-mcp: MCP server for space weather and HF propagation conditions."""

from __future__ import annotations

import sys
from typing import Any

from fastmcp import FastMCP

from . import __version__
from .client import SolarClient

mcp = FastMCP(
    "solar-mcp",
    version=__version__,
    instructions=(
        "MCP server for space weather and HF propagation conditions. "
        "Live solar flux (SFI), Kp index, DSCOVR solar wind, X-ray flux, "
        "space weather alerts, 27-day forecast, and HF band outlook. "
        "All data from NOAA SWPC public endpoints, no authentication required."
    ),
)

_client: SolarClient | None = None


def _get_client() -> SolarClient:
    global _client
    if _client is None:
        _client = SolarClient()
    return _client


# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------


@mcp.tool()
def solar_conditions() -> dict[str, Any]:
    """Get current solar conditions — SFI, Kp, and NOAA space weather scales.

    Returns the latest 10.7 cm solar flux index (SFI), planetary Kp index,
    and NOAA R/S/G scales (radio blackout, solar radiation, geomagnetic storm).
    Includes an HF band outlook derived from current indices.

    Returns:
        Current SFI, Kp, NOAA scales, and band-by-band propagation outlook.
    """
    try:
        return _get_client().conditions()
    except Exception as e:
        return {"error": str(e)}


@mcp.tool()
def solar_forecast() -> dict[str, Any]:
    """Get the NOAA 27-day solar flux and geomagnetic forecast.

    Shows predicted SFI and Kp values for the next 27 days, useful for
    planning DX operations, contests, and POTA/SOTA activations.

    Returns:
        Day-by-day forecast with predicted SFI and Kp values.
    """
    try:
        return _get_client().forecast()
    except Exception as e:
        return {"error": str(e)}


@mcp.tool()
def solar_alerts() -> dict[str, Any]:
    """Get active NOAA space weather alerts and warnings.

    Shows current solar flare alerts, geomagnetic storm warnings,
    radiation storm alerts, and other SWPC bulletins.

    Returns:
        List of active alerts with product ID, issue time, and message text.
    """
    try:
        return _get_client().alerts()
    except Exception as e:
        return {"error": str(e)}


@mcp.tool()
def solar_wind() -> dict[str, Any]:
    """Get real-time DSCOVR L1 solar wind data.

    Shows interplanetary magnetic field (Bz component), solar wind speed,
    and proton density from the DSCOVR satellite at L1 (~1.5M km sunward).
    Southward Bz (negative) drives geomagnetic storms.

    Returns:
        Bz (nT), Bt (nT), wind speed (km/s), density (p/cm³),
        and geomagnetic storm assessment.
    """
    try:
        return _get_client().solar_wind()
    except Exception as e:
        return {"error": str(e)}


@mcp.tool()
def solar_xray() -> dict[str, Any]:
    """Get GOES X-ray flux and solar flare status.

    Shows the current X-ray classification (A, B, C, M, X) from
    GOES satellite data. M and X class flares can cause HF radio blackouts.

    Returns:
        Current flare class, X-ray flux, and HF impact assessment.
    """
    try:
        return _get_client().xray()
    except Exception as e:
        return {"error": str(e)}


@mcp.tool()
def solar_band_outlook() -> dict[str, Any]:
    """Get HF band-by-band propagation outlook based on current conditions.

    Derives a propagation assessment for each HF band (160m through 6m)
    from the current SFI and Kp values. Useful for deciding which band
    to operate on right now.

    Returns:
        Per-band condition rating (Poor/Fair/Good/Excellent) with explanation,
        plus current SFI and Kp values.
    """
    try:
        return _get_client().band_outlook()
    except Exception as e:
        return {"error": str(e)}


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main() -> None:
    """Run the solar-mcp server."""
    transport = "stdio"
    port = 8008
    for i, arg in enumerate(sys.argv[1:], 1):
        if arg == "--transport" and i < len(sys.argv) - 1:
            transport = sys.argv[i + 1]
        if arg == "--port" and i < len(sys.argv) - 1:
            port = int(sys.argv[i + 1])

    if transport == "streamable-http":
        mcp.run(transport=transport, port=port)
    else:
        mcp.run(transport="stdio")


if __name__ == "__main__":
    main()

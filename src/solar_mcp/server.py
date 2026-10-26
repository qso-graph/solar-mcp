"""solar-mcp: MCP server for space weather and HF propagation conditions."""

from __future__ import annotations

import sys
from typing import Any

from fastmcp import FastMCP
from fastmcp.exceptions import ToolError

from . import __spec_version__, __version__
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

# MCP 2026-07-28 tool annotations. The defaults are pessimistic — a tool that
# declares nothing is advertised as destructive, non-idempotent and open-world,
# and the specification tells a client to keep a human in the loop for an
# operation like that. So a client would be entitled to put a confirmation
# prompt in front of reading the solar flux. Every tool here reads NOAA and
# writes nothing, so the three effect hints are the same for all of them; only
# openWorldHint differs, and it is the one that has to be read per tool.
#
# They are a client's UX hint and never a security control: the specification
# requires clients to treat them as untrusted, so none of this replaces the
# input validation in client.py.
_READS_NOAA = {
    "readOnlyHint": True,
    "destructiveHint": False,
    "idempotentHint": True,
    # Reaches services.swpc.noaa.gov, which is outside this host.
    "openWorldHint": True,
}
_ANSWERS_FROM_THE_PACKAGE = {
    "readOnlyHint": True,
    "destructiveHint": False,
    "idempotentHint": True,
    # Reports versions carried in the wheel. It opens no connection, so a
    # client need not treat it as reaching anything.
    "openWorldHint": False,
}


def _version_info_payload() -> dict[str, Any]:
    """Build the version info envelope. Pulled into a helper so tests can
    call it directly without going through the FastMCP wrapper."""
    return {
        "service_name": "solar-mcp",
        "service_version": __version__,
        "spec_version": __spec_version__,
    }


@mcp.tool(annotations=_ANSWERS_FROM_THE_PACKAGE)
def get_version_info() -> dict[str, Any]:
    """Get solar-mcp service version and upstream spec version.

    Returns the running PyPI version of solar-mcp and the NOAA SWPC
    endpoint set revision currently in use. Use this to confirm fleet
    alignment across MCP deployments — agents can compare service_version
    and spec_version across servers to detect drift without going outside
    the MCP protocol.

    Returns:
        service_name, service_version (PyPI), and spec_version (NOAA SWPC
        endpoint set).
    """
    return _version_info_payload()


@mcp.tool(annotations=_READS_NOAA)
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
        raise ToolError(str(e)) from e


@mcp.tool(annotations=_READS_NOAA)
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
        raise ToolError(str(e)) from e


@mcp.tool(annotations=_READS_NOAA)
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
        raise ToolError(str(e)) from e


@mcp.tool(annotations=_READS_NOAA)
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
        raise ToolError(str(e)) from e


@mcp.tool(annotations=_READS_NOAA)
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
        raise ToolError(str(e)) from e


@mcp.tool(annotations=_READS_NOAA)
def solar_band_outlook() -> dict[str, Any]:
    """Get HF band-by-band propagation outlook based on current conditions.

    Derives a propagation assessment for each HF band (160m through 6m)
    from the current SFI and Kp values. Useful for deciding which band
    to operate on right now.

    Each band is rated "<status> — <comment>", the status one of five words
    defined in BAND-OUTLOOK.md: Excellent (wide open, strong long-lasting DX),
    Good (regular DX openings in the band's usual hours), Fair (short, patchy
    or weak openings; DX possible, not dependable), Poor (likely closed for DX,
    or degraded by absorption and noise), Sporadic (not graded from the
    indices: 6m opens by sporadic-E, and by F2 at high solar flux). The
    thresholds are rules of thumb on SFI and Kp, not a propagation model.

    Returns:
        Per-band condition rating with explanation, plus current SFI and Kp
        values.
    """
    try:
        return _get_client().band_outlook()
    except Exception as e:
        raise ToolError(str(e)) from e


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


USAGE = """\
usage: solar-mcp [--transport stdio|streamable-http] [--port N] [--version] [--help]

An MCP server: an AI app (Claude Desktop, Claude Code, ...) starts it and talks
to it over stdio. Run on its own it waits for that app; press Ctrl-C to stop.
Set up a client: https://github.com/qso-graph/solar-mcp#quick-start
"""


def main() -> None:
    """Run the solar-mcp server."""
    # Without this the script ignored both flags and bound stdio, so
    # `--help` left a user watching a banner and a hung terminal.
    if any(a in ("-h", "--help") for a in sys.argv[1:]):
        print(USAGE, end="")
        return
    if "--version" in sys.argv[1:]:
        print(f"solar-mcp {__version__}")
        return
    transport = "stdio"
    port = 8008
    for i, arg in enumerate(sys.argv[1:], 1):
        if arg == "--transport" and i < len(sys.argv) - 1:
            transport = sys.argv[i + 1]
        if arg == "--port" and i < len(sys.argv) - 1:
            port = int(sys.argv[i + 1])

    # Written out rather than passed through: fastmcp takes a literal, and a
    # str that happens to hold the right word is not the same thing.
    if transport == "streamable-http":
        mcp.run(transport="streamable-http", port=port)
    else:
        mcp.run(transport="stdio")


if __name__ == "__main__":
    main()

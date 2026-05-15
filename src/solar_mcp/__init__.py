"""MCP server for solar indices and space weather — SFI, SSN, Kp, DSCOVR, alerts."""

from __future__ import annotations

from importlib.metadata import PackageNotFoundError, version
from typing import Final

try:
    _pkg_version = version("solar-mcp")
except PackageNotFoundError:  # local dev / editable installs without dist metadata
    _pkg_version = "0.0.0-dev"

__version__: Final[str] = _pkg_version

# Upstream data spec the server is bound to. Pinned via the NOAA SWPC public
# endpoint set we consume — bump this when SWPC publishes a new endpoint
# contract (different JSON schema, new feed family, etc.). Reported by the
# get_version_info tool so agents can detect fleet drift without going
# outside the MCP protocol.
__spec_version__: Final[str] = "noaa-swpc-v1"

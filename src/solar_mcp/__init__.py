"""MCP server for solar indices and space weather — SFI, SSN, Kp, DSCOVR, alerts."""

from __future__ import annotations

try:
    from importlib.metadata import version

    __version__ = version("solar-mcp")
except Exception:
    __version__ = "0.0.0-dev"

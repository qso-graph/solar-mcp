# solar-mcp

MCP server for solar indices and space weather -- SFI, SSN, Kp, DSCOVR solar wind, and NOAA alerts.

Part of the [qso-graph](https://qso-graph.io/) collection of amateur radio MCP servers.

## Planned Tools

| Tool | Description |
|------|-------------|
| `solar_current` | Current SFI, SSN, Kp, A-index from NOAA SWPC |
| `solar_forecast` | 3-day solar forecast and geomagnetic outlook |
| `solar_dscovr` | Real-time DSCOVR L1 solar wind (Bz, speed, density) |
| `solar_alerts` | Active NOAA space weather alerts and warnings |
| `solar_history` | Historical solar indices for any date range |

## Install

Coming soon. This package is not yet published to PyPI.

```bash
pip install solar-mcp
```

## Data Source

All data comes from public [NOAA Space Weather Prediction Center (SWPC)](https://www.swpc.noaa.gov/) JSON endpoints. No API key required.

## License

GPL-3.0-or-later. See [LICENSE](LICENSE).

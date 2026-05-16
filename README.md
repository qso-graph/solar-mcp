<!-- mcp-name: io.github.qso-graph/solar-mcp -->
# solar-mcp

[![PyPI](https://img.shields.io/pypi/v/solar-mcp?label=PyPI&color=blue)](https://pypi.org/project/solar-mcp/)
[![MCP Registry](https://img.shields.io/badge/dynamic/json?url=https%3A%2F%2Fregistry.modelcontextprotocol.io%2Fv0%2Fservers%3Fsearch%3Dsolar-mcp&query=%24.servers%5B0%5D.server.version&label=MCP%20Registry&color=blue)](https://registry.modelcontextprotocol.io/v0/servers?search=solar-mcp)

MCP server for space weather and HF propagation conditions — live solar flux, Kp index, DSCOVR solar wind, X-ray flux, alerts, 27-day forecast, and band-by-band outlook through any MCP-compatible AI assistant.

Part of the [qso-graph](https://qso-graph.io/) project. **No authentication required** — all data from [NOAA SWPC](https://www.swpc.noaa.gov/) public endpoints.

> **Version drift?** If the PyPI and MCP Registry badges show different versions, the Registry is catching up to the latest PyPI release on this server's next tag. Forward-only sync — we don't tag content-free releases just to sync. See [qso-graph/.github TEMPLATES.md](https://github.com/qso-graph/.github/blob/main/TEMPLATES.md) for the sync mechanism.

## Install

```bash
pip install solar-mcp
```

## Tools

| Tool | Description |
|------|-------------|
| `solar_conditions` | Current SFI, Kp, and NOAA R/S/G space weather scales |
| `solar_forecast` | 27-day SFI and Kp forecast from NOAA |
| `solar_alerts` | Active space weather alerts and warnings |
| `solar_wind` | Real-time DSCOVR L1 solar wind (Bz, speed, density) |
| `solar_xray` | GOES X-ray flux and solar flare classification |
| `solar_band_outlook` | HF band-by-band propagation assessment (160m-6m) |
| `get_version_info` | Service version + upstream spec version (fleet identity attestation) |

## Quick Start

No credentials needed — just install and configure your MCP client.

### Configure your MCP client

#### Claude Desktop

Add to `claude_desktop_config.json` (`~/Library/Application Support/Claude/` on macOS, `%APPDATA%\Claude\` on Windows):

```json
{
  "mcpServers": {
    "solar": {
      "command": "solar-mcp"
    }
  }
}
```

#### Claude Code

Add to `.claude/settings.json`:

```json
{
  "mcpServers": {
    "solar": {
      "command": "solar-mcp"
    }
  }
}
```

#### ChatGPT Desktop

```json
{
  "mcpServers": {
    "solar": {
      "command": "solar-mcp"
    }
  }
}
```

#### Cursor

Add to `.cursor/mcp.json` (project-level) or `~/.cursor/mcp.json` (global):

```json
{
  "mcpServers": {
    "solar": {
      "command": "solar-mcp"
    }
  }
}
```

#### VS Code / GitHub Copilot

Add to `.vscode/mcp.json` in your workspace:

```json
{
  "servers": {
    "solar": {
      "command": "solar-mcp"
    }
  }
}
```

#### Gemini CLI

Add to `~/.gemini/settings.json` (global) or `.gemini/settings.json` (project):

```json
{
  "mcpServers": {
    "solar": {
      "command": "solar-mcp"
    }
  }
}
```

### Ask questions

> "What are the current solar conditions?"

> "Is the solar wind causing any geomagnetic disturbance?"

> "What's the 27-day solar forecast look like?"

> "Are any bands open right now on HF?"

> "Are there any active space weather alerts?"

> "What class solar flare is happening?"

## Testing Without Network

```bash
SOLAR_MCP_MOCK=1 solar-mcp
```

## MCP Inspector

```bash
solar-mcp --transport streamable-http --port 8008
```

## Development

```bash
git clone https://github.com/qso-graph/solar-mcp.git
cd solar-mcp
pip install -e .
```

## License

GPL-3.0-or-later

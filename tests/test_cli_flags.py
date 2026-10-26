"""The console script answers --help and --version instead of serving.

A script that ignores them binds stdio and waits for JSON-RPC, which leaves a
user watching a FastMCP banner and an apparently hung terminal. Measured against
a fresh `pip install adif-mcp==2.0.1` from PyPI: `adif-mcp --help` was still
running after six seconds with stdin open. Seven servers in this fleet already
behaved correctly and asserted it; this is that assertion.
"""

from __future__ import annotations

from solar_mcp import server


def test_help_and_version_exit_without_serving(capsys, monkeypatch):
    for arg, expect in (
        ("--help", "usage: solar-mcp"),
        ("-h", "usage: solar-mcp"),
        ("--version", "solar-mcp "),
    ):
        monkeypatch.setattr("sys.argv", ["solar-mcp", arg])
        server.main()  # returns instead of serving
        assert expect in capsys.readouterr().out

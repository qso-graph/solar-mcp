"""Conformance with the Model Context Protocol, revision 2026-07-28.

Nothing in this project's documents required this until 2026-10-11 — not
CLAUDE.md, not .claude/rules/security.md, not MCP-SECURITY-FRAMEWORK.md, not
qso-graph-spec. We documented how to *publish* an MCP server in detail and
never wrote down what makes one *valid*, which is how a missing ``isError`` and
missing annotations reached all 22 servers in the fleet unnoticed.

So these are asserted rather than trusted. ``get_version_info`` is the
cautionary case: a convention nobody tested, which drifted across the fleet
before anyone noticed.

Follows ``adif-mcp``'s ``test_mcp_conformance.py``, the reference. What differs
here is ``openWorldHint``: adif-mcp answers wholly from data in its own wheel,
while six of these seven tools read NOAA over the network — so the hint is read
per tool rather than set alike, and ``test_the_server_really_does_reach_noaa``
is the control for the ``True``s.
"""

from __future__ import annotations

import asyncio
import pathlib
import re

import pytest
from fastmcp.exceptions import ToolError

from solar_mcp import server

ANNOTATION_HINTS = ("readOnlyHint", "destructiveHint", "idempotentHint", "openWorldHint")

# The six that read services.swpc.noaa.gov, and the one that does not.
READS_NOAA = {
    "solar_conditions",
    "solar_forecast",
    "solar_alerts",
    "solar_wind",
    "solar_xray",
    "solar_band_outlook",
}
ANSWERS_FROM_THE_PACKAGE = {"get_version_info"}


def _tools() -> dict[str, object]:
    return {t.name: t for t in asyncio.run(server.mcp.list_tools())}


def _wire(tool: object) -> dict[str, object]:
    """The serialised annotations, which is what a client reads.

    Asserted on the wire form rather than the Python attributes: the SDK names
    its fields in snake_case and the protocol does not.
    """
    annotations = getattr(tool, "annotations", None)
    assert annotations is not None, "tool declares no annotations"
    return annotations.model_dump(by_alias=True, exclude_none=True)


def _call(name: str):
    """The underlying function of a registered tool."""
    tool = getattr(server, name)
    return getattr(tool, "fn", tool)


class TestToolAnnotations:
    def test_every_tool_declares_all_four_hints(self) -> None:
        """SOLAR-C01: the defaults are pessimistic, so silence is the wrong answer.

        Omitting them advertises a read-only tool as ``destructiveHint: true``
        and ``openWorldHint: true``, and the specification tells clients to keep
        a human in the loop for operations like that — so a client may
        reasonably put a confirmation prompt in front of reading the solar flux.
        """
        for name, tool in _tools().items():
            wire = _wire(tool)
            for hint in ANNOTATION_HINTS:
                assert hint in wire, f"{name} omits {hint} on the wire; got {sorted(wire)}"

    def test_every_tool_reads_and_none_writes(self) -> None:
        """SOLAR-C02: the three hints that describe effect.

        Every tool here fetches and reports. Nothing in this server writes
        anything, anywhere, so these are the same for all seven.
        """
        for name, tool in _tools().items():
            wire = _wire(tool)
            assert wire["readOnlyHint"] is True, name
            assert wire["destructiveHint"] is False, name
            assert wire["idempotentHint"] is True, name

    def test_open_world_is_read_per_tool(self) -> None:
        """SOLAR-C03: the hint that is not the same for all of them.

        Six tools reach NOAA; ``get_version_info`` reports what the wheel
        carries and opens no connection. Setting them alike would make one of
        the two wrong, whichever value was chosen.
        """
        tools = _tools()
        assert set(tools) == READS_NOAA | ANSWERS_FROM_THE_PACKAGE
        for name in READS_NOAA:
            assert _wire(tools[name])["openWorldHint"] is True, name
        for name in ANSWERS_FROM_THE_PACKAGE:
            assert _wire(tools[name])["openWorldHint"] is False, name

    def test_the_server_really_does_reach_noaa(self) -> None:
        """SOLAR-C04: the control for the six ``openWorldHint: True``.

        A claim in an annotation is worth what the code behind it is worth. The
        inverse of adif-mcp's test of the same name: there, the assertion is
        that no outbound call exists; here, that one does.
        """
        src = pathlib.Path(server.__file__).parent
        outbound = re.compile(r"urllib\.request\.(urlopen|Request)|httpx\.|requests\.(get|post)")
        reached = [p.name for p in src.rglob("*.py")
                   if outbound.search(p.read_text(encoding="utf-8", errors="replace"))]
        assert reached, "no outbound call found, so openWorldHint: True is not honest"

    def test_annotations_are_not_a_security_control(self) -> None:
        """SOLAR-C05: the specification requires clients to treat them as untrusted.

        So they never stand in for validation here. The guard is that the
        values a tool returns are still the client's own parsed values, checked
        by the suites in test_tools.py — this test exists to keep the comment
        in server.py from being the only place that says so.
        """
        assert "never a security control" in pathlib.Path(server.__file__).read_text()


class TestToolErrorsAreFlagged:
    """A tool execution error belongs in the result with ``isError: true``.

    The specification states the cost of getting this wrong: otherwise "the LLM
    would not be able to see that an error occurred and self-correct". These
    returned ``{"error": "..."}`` as a *successful* result until #31, which a
    client cannot tell apart from an answer.
    """

    @pytest.fixture
    def broken(self, monkeypatch):
        """A client whose every call fails the way an unreadable feed does."""
        class Broken:
            def __getattr__(self, _name):
                def fail(*_args, **_kwargs):
                    raise RuntimeError("NOAA SWPC returned no usable data; its format may have changed")
                return fail

        monkeypatch.setattr(server, "_get_client", lambda: Broken())

    @pytest.mark.parametrize("name", sorted(READS_NOAA))
    def test_an_upstream_failure_is_flagged(self, broken, name) -> None:
        """SOLAR-C10: every tool that can fail, not a sample of them.

        Parametrised because the old shape was applied by copy and paste, and a
        single example would have passed while five others still returned a
        dict.
        """
        with pytest.raises(ToolError, match="format may have changed"):
            _call(name)()

    def test_the_message_survives(self, broken) -> None:
        """SOLAR-C11: flagging it is no use if what went wrong is lost.

        The model is meant to act on this, so NOAA's name and the reason stay
        in the message a client receives.
        """
        with pytest.raises(ToolError) as caught:
            _call("solar_conditions")()
        assert "NOAA SWPC" in str(caught.value)

    def test_a_band_outlook_without_indices_is_flagged(self, monkeypatch) -> None:
        """SOLAR-C12: the one error that was raised inside the client.

        ``band_outlook`` is derived from SFI and Kp; with neither it has no
        answer. It used to return ``{"error": ...}`` from client.py, one layer
        below the others.
        """
        from solar_mcp.client import SolarClient

        client = SolarClient()
        monkeypatch.setattr(client, "conditions", lambda: {"sfi": None, "kp": None})
        monkeypatch.setattr(server, "_get_client", lambda: client)
        with pytest.raises(ToolError, match="Unable to fetch current conditions"):
            _call("solar_band_outlook")()


class TestAnAnswerIsNotAnError:
    """The distinction the specification draws, and the easy one to get wrong."""

    def test_a_quiet_sun_is_a_successful_call(self) -> None:
        """SOLAR-C20: "conditions are poor" is an answer, not a failure.

        Conflating the two would make a quiet band report look like a broken
        tool, and a model would retry instead of reporting the verdict.
        """
        answer = _call("solar_conditions")()
        assert isinstance(answer, dict)
        assert "sfi" in answer and "kp" in answer

    def test_a_partial_read_is_a_successful_call_with_a_warning(self, monkeypatch) -> None:
        """SOLAR-C21: one feed unreadable is reported, not raised.

        The client already drew this line — it raises only when *every* feed is
        unreadable — and #31 must not move it. The error shape changed; the
        decision did not.
        """
        from solar_mcp.client import SolarClient

        monkeypatch.delenv("SOLAR_MCP_MOCK", raising=False)
        client = SolarClient()
        monkeypatch.setattr(client, "_get_json", lambda url:
                            [{"flux": 95, "time_tag": "2026-09-28T20:00:00"}]
                            if "10cm-flux" in url else {"unexpected": "shape"})
        monkeypatch.setattr(server, "_get_client", lambda: client)
        answer = _call("solar_conditions")()
        assert answer["sfi"] == 95
        assert answer["warnings"]


class TestVersionInfoShape:
    def test_it_matches_the_shape_the_fleet_returns(self) -> None:
        """SOLAR-C30: the convention that drifted because nobody asserted it."""
        info = _call("get_version_info")()
        assert info["service_name"] == "solar-mcp"
        assert info["service_version"]
        assert info["spec_version"]


class TestRegistration:
    def test_the_seven_tools_a_client_sees(self) -> None:
        """SOLAR-C40: calling a function directly is not proof a client can."""
        assert set(_tools()) == {
            "get_version_info",
            "solar_conditions",
            "solar_forecast",
            "solar_alerts",
            "solar_wind",
            "solar_xray",
            "solar_band_outlook",
        }

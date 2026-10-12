"""solar-mcp read over the NOAA responses QSO Graph Desktop is tested against.

Issue #28. The Conditions card on Desktop's Home follows `SolarClient`, so
solar-mcp is the specification for its behaviour (`QGD-HOM-0008`). Holding both
to the same recorded bytes is what makes that true rather than merely stated:
a change to the parsing here shows up as a disagreement, instead of the two
drifting until someone compares them by hand.

The three NOAA files are byte-identical to Desktop's copies and asserted so.
`expected.json` is not — see `fixtures/noaa/README.md`.

Test IDs: SOLAR-FIX-001 onward.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from solar_mcp.client import SolarClient

FIXTURES = Path(__file__).parent / "fixtures" / "noaa"

# Recorded from qso-graph-desktop/tests/fixtures/noaa on 2026-10-12. These are
# the bytes both projects read; a difference means the pair has drifted apart
# and the answers either side computes are no longer comparable.
DESKTOP_SUMS = {
    "quiet/10cm-flux.json": "2138583f6f96a59ab0c9f43cfec454b0cd844cccfaa36c1f3631c2d413d20858",
    "quiet/noaa-planetary-k-index.json":
        "9eb4122adc5d795965b528c70a766cfaab2f4f389d9364bccdf0bb22a0fdd239",
    "quiet/noaa-scales.json":
        "62c3233ad19470a76e19c9205b02419c3d7340e2f8205373d10b24621576d4c4",
    "storm/10cm-flux.json": "47463078883fd10daee99f72e16d6ee2cf29cf974f8a35133ce4c5443be4a0ce",
    "storm/noaa-planetary-k-index.json":
        "ea45dc16d611a72645a1a2a39297e0c8bfa4e2c417235e311bb4c9c7264460cb",
    "storm/noaa-scales.json":
        "f2d1b143dc4d726c0ff35a745ba9f64e4e775d20c07d54753c0879fc04539b79",
}

# What conditions() asks NOAA for, and which recorded file answers it.
BY_ENDPOINT = {
    "10cm-flux": "10cm-flux.json",
    "noaa-planetary-k-index": "noaa-planetary-k-index.json",
    "noaa-scales": "noaa-scales.json",
}


def _client_over(variant: str, monkeypatch: pytest.MonkeyPatch) -> SolarClient:
    """A client that reads the recorded responses instead of reaching NOAA."""
    monkeypatch.delenv("SOLAR_MCP_MOCK", raising=False)
    client = SolarClient()

    def recorded(url: str):
        for endpoint, filename in BY_ENDPOINT.items():
            if endpoint in url:
                return json.loads((FIXTURES / variant / filename).read_text())
        raise AssertionError(f"conditions() asked for an unrecorded endpoint: {url}")

    monkeypatch.setattr(client, "_get_json", recorded)
    return client


def _expected(variant: str) -> dict:
    return json.loads((FIXTURES / variant / "expected.json").read_text())


class TestTheFixturesAreTheSameBytes:
    @pytest.mark.parametrize("name,digest", sorted(DESKTOP_SUMS.items()))
    def test_a_noaa_response_matches_desktops_copy(self, name: str, digest: str) -> None:
        """SOLAR-FIX-001: the point of sharing them is that they do not drift.

        Only the NOAA responses are compared. `expected.json` is ours to change
        when the answer changes, which #28 is an instance of.
        """
        actual = hashlib.sha256((FIXTURES / name).read_bytes()).hexdigest()
        assert actual == digest, (
            f"{name} differs from QSO Graph Desktop's copy; the two must be updated together"
        )


class TestConditionsOverTheRecordedResponses:
    @pytest.mark.parametrize("variant", ["quiet", "storm"])
    def test_every_value_expected_json_declares(self, variant, monkeypatch) -> None:
        """SOLAR-FIX-010: the agreed answer, field by field.

        Compared over the keys `expected.json` declares rather than by equality,
        so either side may report more — solar-mcp reports `a_index` since #28
        — without the other having to change.
        """
        answer = _client_over(variant, monkeypatch).conditions()
        expected = _expected(variant)
        for key, value in expected.items():
            if key in ("producedBy", "bands"):
                continue
            assert answer[key] == value, f"{variant}/{key}"
        assert answer["band_outlook"]["bands"] == expected["bands"], variant


class TestScaleLevelsCarryTheirLetter:
    """Issue #28, item 2 — the defect these fixtures were what exposed."""

    def test_a_quiet_day_reads_r0_s0_g0(self, monkeypatch) -> None:
        """SOLAR-FIX-020: unchanged, and the control for the one below."""
        answer = _client_over("quiet", monkeypatch).conditions()
        assert answer["noaa_r_scale"] == "R0"
        assert answer["noaa_s_scale"] == "S0"
        assert answer["noaa_g_scale"] == "G0"

    def test_a_storm_reads_g2_not_2(self, monkeypatch) -> None:
        """SOLAR-FIX-021: the bug.

        NOAA sends the level as a bare digit. Only "0" was prefixed, so the one
        reading that matters — a storm — lost the letter saying which scale it
        belonged to, and "2" could as easily have been R2 or S2.
        """
        answer = _client_over("storm", monkeypatch).conditions()
        assert answer["noaa_g_scale"] == "G2"

    def test_a_level_under_the_wrong_letter_is_refused(self, monkeypatch) -> None:
        """SOLAR-FIX-022: a prefixed value is kept only under its own letter.

        "G2" arriving in the R slot is not an R-scale reading, and reporting it
        as one would be worse than reporting nothing.
        """
        from solar_mcp.client import _scale

        assert _scale("R", "G2") == "unknown"
        assert _scale("G", "G2") == "G2"
        assert _scale("G", None) == "unknown"
        assert _scale("G", "") == "unknown"


class TestTheAIndexIsReported:
    """Issue #28, item 3 — already in the feed that was being read."""

    @pytest.mark.parametrize("variant,expected", [("quiet", 6.0), ("storm", 6.0)])
    def test_it_comes_from_the_kp_feed(self, variant, expected, monkeypatch) -> None:
        """SOLAR-FIX-030: `a_running` rides along in the rows Kp is read from.

        Hams read A beside K, so reporting it costs nothing and saves the card
        a request it would otherwise have no source for.
        """
        answer = _client_over(variant, monkeypatch).conditions()
        assert answer["a_index"] == expected


class TestAnUnusableTimeIsNotPassedThrough:
    """Issue #28, the one noticed while porting."""

    def test_an_impossible_date_is_dropped_and_warned(self, monkeypatch) -> None:
        """SOLAR-FIX-040: February has no 30th.

        Such a value was reported as the time of the reading, dating it wrongly.
        The reading itself still stands — only its time is dropped — and the
        warning says what arrived, so a format change is visible.
        """
        monkeypatch.delenv("SOLAR_MCP_MOCK", raising=False)
        client = SolarClient()
        monkeypatch.setattr(client, "_get_json", lambda url:
                            [{"flux": 122, "time_tag": "2026-02-30T21:00:00"}]
                            if "10cm-flux" in url else
                            ([{"time_tag": "2026-10-11T18:00:00", "Kp": 1.67, "a_running": 6}]
                             * 2 if "k-index" in url else {}))
        answer = client.conditions()
        assert answer["sfi"] == 122
        assert answer["sfi_timestamp"] is None
        assert any("not a usable time" in w for w in answer["warnings"])

    def test_a_real_time_survives_unchanged(self, monkeypatch) -> None:
        """SOLAR-FIX-041: the control — this refuses a date, not every date."""
        answer = _client_over("quiet", monkeypatch).conditions()
        assert answer["sfi_timestamp"] == "2026-10-11T20:00:00"
        assert answer["kp_timestamp"] == "2026-10-11T18:00:00"
        assert "warnings" not in answer

"""NOAA SWPC's request limits: the refresh floors, and what a 429 does.

These assert the three mechanisms of guarantee 8 separately, because they were
once conflated: a refresh floor bounds how often we may ask, the spacing
constant bounds how closely two asks may land, and a 429 is NOAA SWPC stating
its limit at runtime. See qso-graph-devel/planning/MCP-SECURITY-FRAMEWORK.md.
"""

from __future__ import annotations

import urllib.error
from email.message import Message

import pytest

from solar_mcp import client as c

_URL = "https://services.swpc.noaa.gov/products/alerts.json"


def _headers(**kw: str) -> Message:
    m = Message()
    for k, v in kw.items():
        m[k.replace("_", "-")] = v
    return m


def _http_error(code: int, **headers: str) -> urllib.error.HTTPError:
    return urllib.error.HTTPError(_URL, code, "nope", _headers(**headers), None)


# --- the refresh floors ----------------------------------------------------


def test_refresh_floors_are_the_agreed_figures() -> None:
    """Asserted because a TTL is the limit that actually decides how many
    requests a day this server can cause, and it is a one-character edit away
    from being much smaller."""
    assert c._CONDITIONS_TTL == 900.0
    assert c._FORECAST_TTL == 3600.0
    assert c._ALERTS_TTL == 300.0
    assert c._WIND_TTL == 300.0
    assert c._XRAY_TTL == 300.0


def test_spacing_is_distinct_from_the_floors() -> None:
    """A gap between calls, not a staleness bound -- different magnitudes."""
    assert c._MIN_DELAY > 0


# --- Retry-After parsing ---------------------------------------------------


@pytest.mark.parametrize(
    "header,expected",
    [
        (None, c._MIN_BACKOFF),       # absent: wait the floor, do not guess
        ("", c._MIN_BACKOFF),
        ("0", c._MIN_BACKOFF),        # a provider saying "now" still gets a floor
        ("5", c._MIN_BACKOFF),        # below the floor is raised to it
        ("300", 300.0),               # honoured as stated
        ("99999", c._MAX_BACKOFF),    # above the ceiling is capped
        ("Wed, 21 Oct 2026 07:28:00 GMT", c._MIN_BACKOFF),  # date form unparsed
        ("garbage", c._MIN_BACKOFF),
    ],
)
def test_retry_after_is_honoured_within_bounds(
    header: str | None, expected: float
) -> None:
    assert c._retry_after(header) == expected


# --- what a 429 does -------------------------------------------------------


def test_429_raises_rate_limited_and_names_the_wait(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        c.urllib.request,
        "urlopen",
        lambda *a, **k: (_ for _ in ()).throw(_http_error(429, Retry_After="120")),
    )
    cl = c.SolarClient()
    with pytest.raises(c.RateLimited) as e:
        cl._get_json(_URL)
    assert e.value.retry_after == 120
    assert "120" in str(e.value)


def test_429_blocks_later_calls_without_asking(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The point of honouring the limit: the next call must not go out."""
    calls: list[str] = []

    def boom(*a: object, **k: object) -> None:
        calls.append("sent")
        raise _http_error(429, Retry_After="120")

    monkeypatch.setattr(c.urllib.request, "urlopen", boom)
    cl = c.SolarClient()
    with pytest.raises(c.RateLimited):
        cl._get_json(_URL)
    assert calls == ["sent"]

    # A different path: the block is client-wide, as the provider's view of us is.
    with pytest.raises(c.RateLimited):
        cl._get_json(_URL + "/other")
    assert calls == ["sent"], "a second request was sent while blocked"


def test_block_expires(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: list[str] = []

    class Resp:
        def read(self) -> bytes:
            seen.append("sent")
            return b"[]"

        def __enter__(self) -> "Resp":
            return self

        def __exit__(self, *a: object) -> None:
            return None

    monkeypatch.setattr(c.urllib.request, "urlopen", lambda *a, **k: Resp())
    cl = c.SolarClient()
    cl._blocked_until = 0.0  # as if the wait has passed
    assert cl._get_json(_URL) == []
    assert seen == ["sent"]


def test_bare_503_is_an_outage_not_a_limit(monkeypatch: pytest.MonkeyPatch) -> None:
    """Without Retry-After a 503 is the provider being down, and must not
    block the client."""
    monkeypatch.setattr(
        c.urllib.request,
        "urlopen",
        lambda *a, **k: (_ for _ in ()).throw(_http_error(503)),
    )
    cl = c.SolarClient()
    with pytest.raises(RuntimeError) as e:
        cl._get_json(_URL)
    assert not isinstance(e.value, c.RateLimited)
    assert cl._blocked_until == 0.0


def test_503_with_retry_after_is_a_limit(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        c.urllib.request,
        "urlopen",
        lambda *a, **k: (_ for _ in ()).throw(_http_error(503, Retry_After="90")),
    )
    cl = c.SolarClient()
    with pytest.raises(c.RateLimited) as e:
        cl._get_json(_URL)
    assert e.value.retry_after == 90


def test_network_failure_still_names_the_provider(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The named-error behaviour must survive: the message says what was being
    reached, so a model can tell an outage from a defect here."""
    monkeypatch.setattr(
        c.urllib.request,
        "urlopen",
        lambda *a, **k: (_ for _ in ()).throw(urllib.error.URLError("refused")),
    )
    cl = c.SolarClient()
    with pytest.raises(RuntimeError, match='NOAA SWPC request failed'):
        cl._get_json(_URL)

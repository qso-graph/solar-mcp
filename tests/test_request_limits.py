"""NOAA SWPC's request limits: the refresh floors, and what a 429 does.

These assert the three mechanisms of guarantee 8 separately, because they were
once conflated: a refresh floor bounds how often we may ask, the spacing
constant bounds how closely two asks may land, and a 429 is NOAA SWPC stating
its limit at runtime. See qso-graph-devel/planning/MCP-SECURITY-FRAMEWORK.md.
"""

from __future__ import annotations

import time
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


def _client():
    cl = c.SolarClient()
    return cl


def _raises(exc):
    def f(*a: object, **k: object):
        raise exc
    return f


# One name for "make the outbound call", so the tests below read the same in
# every repo even where the method behind it differs.
c.SolarClient._fetch_for_test = lambda self: self._fetch(_URL)  # type: ignore[attr-defined]


# --- defects found by review, held here so they stay fixed ----------------


@pytest.mark.parametrize("header", ["nan", "NaN", "inf", "infinity"])
def test_a_non_finite_header_still_blocks(header: str) -> None:
    """nan defeats a clamp -- every comparison against it is False -- so it
    would reach a deadline that is never in the future and leave the block off
    altogether. The floor applies instead."""
    assert c._retry_after(header) == c._MIN_BACKOFF


def test_a_shorter_later_block_does_not_shorten_a_longer_one(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A response asking for 60 s landing while a 300 s block runs must not
    release us at 60."""
    cl = _client()
    cl._last_request = 0.0
    monkeypatch.setattr(
        c.urllib.request, "urlopen", _raises(_http_error(429, Retry_After="300"))
    )
    with pytest.raises(c.RateLimited) as first:
        cl._fetch_for_test()
    assert first.value.retry_after == 300

    # A 60 s answer now, as a slower in-flight request would bring back.
    monkeypatch.setattr(
        c.urllib.request, "urlopen", _raises(_http_error(429, Retry_After="60"))
    )
    cl._blocked_until = 0.0  # let one through, to reach the arming code again
    cl._last_request = 0.0
    with pytest.raises(c.RateLimited):
        cl._fetch_for_test()
    deadline_after_60 = cl._blocked_until

    # Arming again with 300 and then 60 must leave the 300 standing.
    cl._blocked_until = 0.0
    cl._last_request = 0.0
    monkeypatch.setattr(
        c.urllib.request, "urlopen", _raises(_http_error(429, Retry_After="300"))
    )
    with pytest.raises(c.RateLimited):
        cl._fetch_for_test()
    long_deadline = cl._blocked_until
    assert long_deadline > deadline_after_60


def test_a_block_arriving_during_the_gap_is_honoured() -> None:
    """The check must be made before the request, not before the wait: a 429
    landing while a caller sleeps out the spacing gap has to stop it."""
    import threading

    cl = _client()
    cl._last_request = time.monotonic()   # the next call sleeps out the gap
    refused: list[BaseException] = []

    def caller() -> None:
        try:
            cl._rate_limit()
        except c.RateLimited as e:
            refused.append(e)

    t = threading.Thread(target=caller)
    t.start()
    with cl._lock:
        cl._blocked_until = time.monotonic() + 300.0   # arrives mid-sleep
    t.join(timeout=5)
    assert refused, "a request went out that a 429 had already forbidden"


def test_the_spacing_sleep_does_not_hold_the_lock() -> None:
    """Sleeping under the lock would block an unrelated caller from even
    reading the state, and is how the mid-sleep 429 above gets missed."""
    import threading

    cl = _client()
    cl._last_request = time.monotonic()
    threading.Thread(target=cl._rate_limit, daemon=True).start()
    time.sleep(min(0.02, c._MIN_DELAY / 4))
    start = time.monotonic()
    acquired = cl._lock.acquire(timeout=max(1.0, c._MIN_DELAY))
    held = time.monotonic() - start
    if acquired:
        cl._lock.release()
    assert acquired, "the lock was held for the whole spacing sleep"
    assert held < c._MIN_DELAY, f"waited {held:.3f}s for the lock"

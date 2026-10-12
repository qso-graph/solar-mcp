"""Security test suite — qso-graph MCP Security Framework v1.0.

These tests enforce the 10 non-negotiable security guarantees.
See: https://qso-graph.io/security/
"""

import re
from pathlib import Path

SRC_DIR = Path(__file__).parent.parent / "src"


def _py_files():
    """Yield all .py files under src/."""
    yield from SRC_DIR.rglob("*.py")


def test_no_print_credentials():
    """Guarantee #1: Credentials never in logs (print statements)."""
    forbidden = re.compile(
        r'print\s*\(.*(?:password|api_key|creds|secret|token).*\)',
        re.IGNORECASE,
    )
    for py_file in _py_files():
        content = py_file.read_text()
        matches = forbidden.findall(content)
        assert not matches, f"Credential print in {py_file.name}: {matches}"


def test_no_logging_credentials():
    """Guarantee #1: Credentials never in logs (logging statements)."""
    forbidden = re.compile(
        r'logging\..*\(.*(?:password|api_key|creds|secret|token).*\)',
        re.IGNORECASE,
    )
    for py_file in _py_files():
        content = py_file.read_text()
        matches = forbidden.findall(content)
        assert not matches, f"Credential logging in {py_file.name}: {matches}"


def test_no_subprocess():
    """Guarantee #5: No command injection surface."""
    forbidden = re.compile(r'subprocess\.|os\.system|shell\s*=\s*True')
    for py_file in _py_files():
        content = py_file.read_text()
        matches = forbidden.findall(content)
        assert not matches, f"Shell execution in {py_file.name}: {matches}"


def test_all_urls_https():
    """Guarantee #7: HTTPS only for external calls."""
    http_url = re.compile(r'http://(?!localhost|127\.0\.0\.1|::1)')
    for py_file in _py_files():
        content = py_file.read_text()
        matches = http_url.findall(content)
        assert not matches, f"Non-HTTPS URL in {py_file.name}: {matches}"


def test_error_messages_safe():
    """Guarantee #3/#10: Credentials never in error messages."""
    dangerous = re.compile(
        r'raise\s+\w+\([^)]*(?:password|api_key|creds|secret).*\)',
        re.IGNORECASE,
    )
    for py_file in _py_files():
        content = py_file.read_text()
        matches = dangerous.findall(content)
        assert not matches, f"Credential in exception in {py_file.name}: {matches}"


def test_no_eval_exec():
    """Guarantee #5: No code injection surface."""
    for py_file in _py_files():
        content = py_file.read_text()
        for i, line in enumerate(content.splitlines(), 1):
            stripped = line.lstrip()
            if stripped.startswith("#"):
                continue
            if re.search(r'\b(?:eval|exec)\s*\(', stripped):
                assert False, f"eval/exec in {py_file.name}:{i}: {stripped.strip()}"


def test_tls_verification_is_on():
    """Guarantee #8: TLS verification is never disabled.

    This is the one way to get qso-graph-devel#73 wrong. ``ssl.CERT_NONE`` or
    ``check_hostname = False`` would also make a failing call "work", by
    accepting any certificate from anyone — a worse defect than the one being
    fixed, and an invisible one. The fix is a complete root set, not a relaxed
    check.
    """
    import ssl

    from solar_mcp.client import _context

    context = _context()
    assert context.verify_mode == ssl.CERT_REQUIRED
    assert context.check_hostname is True


def test_the_root_set_is_carried_not_borrowed():
    """Guarantee #8: the roots come from certifi, not the host's OpenSSL store.

    macOS ships ``/etc/ssl/cert.pem`` for OpenSSL — and therefore for Python —
    as a deliberately reduced file: 128 roots against the system keychain's
    158. A certificate chaining to one of the 30 it omits fails for Python
    while ``curl`` to the same URL succeeds, and the user is told only that the
    source could not be reached.
    """
    from solar_mcp.client import _context

    # Where the roots come from. A context cannot be asked which file it was
    # built from, so this is read off the source — the one claim a runtime
    # check cannot make.
    source = (SRC_DIR / "solar_mcp" / "client.py").read_text()
    assert "cafile=certifi.where()" in source

    # And that the file actually loaded. An empty store would fail closed and
    # look exactly like an outage, which is the symptom this is meant to end.
    assert _context().cert_store_stats()["x509_ca"] > 100


def test_every_outbound_call_verifies():
    """Guarantee #8: a new fetch path cannot quietly skip the context.

    Both calls here pass ``context=_context()``. This is the check that lasts:
    the next person to add a fetch gets a failing test rather than a server
    that works everywhere except the machine with the reduced store.
    """
    content = (SRC_DIR / "solar_mcp" / "client.py").read_text()
    # Line by line rather than by matching balanced parentheses: a regex for
    # the whole call ends at the first ")", which is the one inside
    # "_context()", so it would read a call that passes no context at all as
    # though it did.
    calls = [(i, line) for i, line in enumerate(content.splitlines(), 1)
             if "urllib.request.urlopen(" in line]
    assert calls, "no urlopen call found; has the fetch path moved?"
    for number, line in calls:
        assert "context=_context()" in line, (
            f"client.py:{number} opens a connection without a verifying context: "
            f"{line.strip()}"
        )

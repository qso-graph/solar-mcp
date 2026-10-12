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


def _code_only(path: Path) -> str:
    """The file with comments and string literals removed.

    Some of these checks must read what the code *does*, not what it says about
    itself. `_context()` carries a docstring explaining that `ssl.CERT_NONE`
    would be the wrong fix, and a plain text search cannot tell that sentence
    apart from the thing it warns against.
    """
    import tokenize

    kept = []
    with path.open("rb") as handle:
        for token in tokenize.tokenize(handle.readline):
            if token.type in (tokenize.COMMENT, tokenize.STRING):
                continue
            kept.append(token.string)
    return " ".join(kept)


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


def test_tls_verification_is_never_disabled():
    """Guarantee #8: no context here stops checking certificates.

    ``ssl.CERT_NONE`` or ``check_hostname = False`` would make a failing call
    "work", by accepting any certificate from anyone — a worse defect than the
    one qso-graph-devel#73 fixes, and an invisible one. The fix is a complete
    root set, not a relaxed check.

    Read off the source, like every check in this file: the release gate runs it
    with the package *not installed* (`pip install pytest pip-audit`), so nothing
    here may import `solar_mcp`. The runtime assertions — that the built context
    really is CERT_REQUIRED with check_hostname on — live in test_tools.py, which
    CI runs with the package present. Both are needed; neither replaces the other.
    """
    forbidden = re.compile(r"CERT_NONE|check_hostname\s*=\s*False|_create_unverified")
    for py_file in _py_files():
        matches = forbidden.findall(_code_only(py_file))
        assert not matches, f"TLS verification weakened in {py_file.name}: {matches}"


def test_the_root_set_is_carried_not_borrowed():
    """Guarantee #8: the roots come from certifi, not the host's OpenSSL store.

    macOS ships ``/etc/ssl/cert.pem`` for OpenSSL — and therefore for Python —
    as a deliberately reduced file: 128 roots against the system keychain's
    158. A certificate chaining to one of the 30 it omits fails for Python
    while ``curl`` to the same URL succeeds, and the user is told only that the
    source could not be reached.
    """
    client = (SRC_DIR / "solar_mcp" / "client.py").read_text()
    assert "cafile=certifi.where()" in client


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

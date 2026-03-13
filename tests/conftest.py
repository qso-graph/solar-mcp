"""Shared pytest configuration for solar-mcp."""
import pytest

def pytest_addoption(parser):
    parser.addoption("--live", action="store_true", default=False, help="Run live API integration tests")

def pytest_configure(config):
    config.addinivalue_line("markers", "live: mark test as requiring live API access")

def pytest_collection_modifyitems(config, items):
    if not config.getoption("--live"):
        skip_live = pytest.mark.skip(reason="Live tests disabled (use --live)")
        for item in items:
            if "live" in item.keywords:
                item.add_marker(skip_live)

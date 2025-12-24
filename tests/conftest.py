"""Pytest configuration and fixtures."""

import pytest


def pytest_addoption(parser: pytest.Parser) -> None:
    """Add custom command line options for pytest."""
    parser.addoption(
        "--run-slow-tests",
        action="store_true",
        default=False,
        help="Run tests marked as slow",
    )
    parser.addoption(
        "--run-integration-tests",
        action="store_true",
        default=False,
        help="Run tests marked as integration",
    )


def pytest_configure(config: pytest.Config) -> None:
    """Configure pytest with custom markers."""
    config.addinivalue_line("markers", "slow: marks tests as slow")
    config.addinivalue_line("markers", "integration: marks tests as integration tests")


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    """Modify test collection based on command line options."""
    run_slow = config.getoption("--run-slow-tests")
    run_integration = config.getoption("--run-integration-tests")

    skip_slow = pytest.mark.skip(reason="need --run-slow-tests option to run")
    skip_integration = pytest.mark.skip(reason="need --run-integration-tests option to run")

    for item in items:
        if "slow" in item.keywords and not run_slow:
            item.add_marker(skip_slow)
        if "integration" in item.keywords and not run_integration:
            item.add_marker(skip_integration)


# Convenience marker decorators
slow_test = pytest.mark.slow
integration_test = pytest.mark.integration

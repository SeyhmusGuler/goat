import time

import pytest

from tests.conftest import integration_test, slow_test


@pytest.mark.parametrize("x", [1, 2, 3])
def test_placeholder(x: int) -> None:
    assert x > 0


@integration_test
def test_integration_placeholder() -> None:
    time.sleep(3)
    assert True


@slow_test
def test_slow_placeholder() -> None:
    time.sleep(5)
    assert True

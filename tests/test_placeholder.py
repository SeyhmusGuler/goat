import pytest


@pytest.mark.parametrize("x", [1, 2, 3])
def test_placeholder(x: int) -> None:
    assert x > 0

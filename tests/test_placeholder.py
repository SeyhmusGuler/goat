import pytest

from goat.placeholder import multiply_by_2


def test_multiply_by_2():
    assert multiply_by_2(3) == 6
    with pytest.raises(TypeError):
        _ = multiply_by_2("3")
        _ = multiply_by_2(3.0)

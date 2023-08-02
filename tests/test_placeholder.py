import pytest

from goat.placeholder import multiply_by_2, add_two


def test_multiply_by_2():
    assert multiply_by_2(3) == 6
    with pytest.raises(TypeError):
        _ = multiply_by_2("3")
        _ = multiply_by_2(3.0)


def test_add_two_valid():
    assert add_two(3) == 5
    assert add_two(0.0) == 2


def test_add_two_invalid_input():
    with pytest.raises(TypeError):
        _ = add_two("3")
        _ = add_two(True)

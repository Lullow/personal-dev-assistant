from demo_challenges.stats_utils import average


def test_average_returns_decimal_value():
    assert average([1, 2]) == 1.5

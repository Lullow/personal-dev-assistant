from demo_challenges.string_utils import normalize_name


def test_normalize_name_strips_spaces_and_title_cases():
    assert normalize_name("  eLIA  ") == "Elia"

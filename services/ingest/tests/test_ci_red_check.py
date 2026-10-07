def test_ci_red_check_deliberate_failure():
    assert 1 == 2, "deliberate failure to prove CI turns red"

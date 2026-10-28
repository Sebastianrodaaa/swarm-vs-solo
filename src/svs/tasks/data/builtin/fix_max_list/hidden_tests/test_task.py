from listops import max_in_list

def test_max_in_list():
    assert max_in_list([1, 9, 3]) == 9
    assert max_in_list([-5, -1]) == -1

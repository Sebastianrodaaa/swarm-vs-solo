from listops import merge_sorted

def test_merge_sorted():
    assert merge_sorted([1, 3], [2, 4]) == [1, 2, 3, 4]

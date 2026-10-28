from search import binary_search

def test_binary_search():
    arr = [1, 3, 5, 7, 9]
    assert binary_search(arr, 5) == 2
    assert binary_search(arr, 2) == -1

from text import word_count

def test_word_count():
    assert word_count('one two three') == 3
    assert word_count('  hi   there ') == 2

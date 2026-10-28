from fizzbuzz import fizzbuzz

def test_fizzbuzz():
    assert fizzbuzz(5) == ['1','2','Fizz','4','Buzz']
    assert fizzbuzz(15)[-1] == 'FizzBuzz'

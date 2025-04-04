# sample_code.py

def factorial(n):
    """Calculate the factorial of n."""
    if n < 0:
        return None
    elif n == 0:
        return 1
    else:
        result = 1
        for i in range(1, n + 1):
            result *= i
        return result

def main():
    # Input handling with exception handling
    try:
        x = int(input("Enter a number: "))
    except ValueError:
        print("Invalid input. Please enter an integer.")
        return

    # Conditional check for negative numbers
    if x < 0:
        print("Negative numbers are not allowed.")
    else:
        print("Factorial of", x, "is", factorial(x))
    
    # A while loop example with a continue statement
    count = 0
    while count < 5:
        if count == 3:
            count += 1
            continue
        print("Current count:", count)
        count += 1

if __name__ == '__main__':
    main()

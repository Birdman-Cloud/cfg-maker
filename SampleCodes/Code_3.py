def is_even(num):
    """Check if a number is even."""
    if num % 2 == 0:
        return True
    else:
        return False

def factorial(n):
    """Calculate the factorial of a number recursively."""
    if n <= 0:
        return 1
    else:
        return n * factorial(n - 1)

def main():
    """Main function to demonstrate control flow."""
    numbers = [1, 2, 3, 4, 5]
    for num in numbers:
        if is_even(num):
            print(f"{num} is even")
        else:
            print(f"{num} is odd")
    
    try:
        result = factorial(5)
        print(f"Factorial of 5 is {result}")
    except RecursionError:
        print("Recursion depth exceeded")

    # While loop example
    count = 0
    while count < 3:
        print(f"Count: {count}")
        count += 1

if __name__ == "__main__":
    main()
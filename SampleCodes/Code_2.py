# sample_code.py
"""
A sample Python file of moderate complexity to demonstrate
Control Flow Graph (CFG) generation.

This file includes functions, loops, conditionals, exception handling,
and a simple class.
"""

import random
import time

# --- Constants and Globals ---
MAX_ITERATIONS = 10
ERROR_RATE = 0.1 # Probability of simulated error

# --- Simple Class ---
class TaskRunner:
    """Simulates running tasks with potential failures."""
    def __init__(self, name):
        self.name = name
        self.tasks_completed = 0
        self.tasks_failed = 0
        print(f"TaskRunner '{self.name}' initialized.")

    def run_task(self, task_id):
        """Simulates running a single task."""
        print(f"  {self.name}: Starting task {task_id}...")
        time.sleep(0.01) # Simulate work

        # Simulate a potential error
        if random.random() < ERROR_RATE:
            self.tasks_failed += 1
            print(f"  {self.name}: Error occurred during task {task_id}!")
            raise ValueError(f"Simulated failure in task {task_id}")

        # Simulate task success
        self.tasks_completed += 1
        print(f"  {self.name}: Task {task_id} completed successfully.")
        return True


# --- Core Logic Function ---
def process_batch(runner, batch_size):
    """
    Processes a batch of tasks using the TaskRunner.

    Handles exceptions and uses loops and conditionals.
    """
    print(f"\n--- Processing Batch (Size: {batch_size}) with {runner.name} ---")
    if batch_size <= 0:
        print("Error: Batch size must be positive.")
        return {"status": "error", "reason": "invalid batch size"}

    successful_runs = 0
    for i in range(batch_size):
        task_number = i + 1
        print(f"\nAttempting Task {task_number}/{batch_size}")

        # Example of a conditional break
        if runner.tasks_failed > batch_size // 2:
             print("Stopping batch early due to excessive failures.")
             break # Exit the for loop

        # Example of a conditional continue
        if task_number % 5 == 0:
             print("Skipping task number divisible by 5.")
             continue # Skip to the next iteration

        try:
            # Call the method on the runner object
            success = runner.run_task(task_number)
            if success:
                successful_runs += 1

        except ValueError as ve:
            # Handle the specific simulated error
            print(f"Caught expected error: {ve}")
            # Continue processing the rest of the batch
        except Exception as e:
            # Handle unexpected errors
            print(f"Caught unexpected error: {e}")
            # Decide whether to break, continue, or log differently
        finally:
            # This code runs whether an exception occurred or not
            print(f"Finished processing attempt for task {task_number}.")

    # Loop finished or broken
    print("\n--- Batch Processing Finished ---")
    print(f"Runner Stats: Completed={runner.tasks_completed}, Failed={runner.tasks_failed}")

    # Return results based on processing outcome
    if successful_runs > batch_size * 0.75:
        final_status = "excellent"
    elif successful_runs > batch_size * 0.5:
        final_status = "good"
    else:
        final_status = "poor"

    return {
        "status": final_status,
        "successful_runs": successful_runs,
        "total_attempts": runner.tasks_completed + runner.tasks_failed # Note: this might differ from batch_size if 'continue' or 'break' used
    }


# --- Helper Function ---
def check_status(result_dict):
    """Simple function to check the status from the results."""
    if not result_dict:
        print("No results to check.")
        return False

    status = result_dict.get("status", "unknown")
    if status == "excellent" or status == "good":
        print(f"Overall status is positive: {status}")
        return True
    else:
        print(f"Overall status is not positive: {status}")
        return False


# --- Main Execution Area ---
if __name__ == "__main__":
    print("Starting the sample script...")

    # Create an instance of the class
    my_runner = TaskRunner("MainRunner")

    # Define the batch size
    num_tasks = random.randint(5, MAX_ITERATIONS) # Random batch size

    # Run the main processing function
    results = process_batch(my_runner, num_tasks)

    # Use the helper function
    is_ok = check_status(results)

    print(f"\nScript finished. Was status OK? {is_ok}")
# cfg_generator.py
import argparse
import os
import tempfile
import logging
import subprocess # Still potentially needed if graphviz library uses it indirectly
import shutil    # Needed for cleanup
import graphviz  # Needed for the basic diagnostic test

# --- Configuration ---
# Configure basic logging (using a more detailed format for better debugging)
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(name)s - %(message)s')
logger = logging.getLogger(__name__) # Use a specific logger

# --- Core Generation Logic ---

def _generate_and_visualize_cfg(input_py_path, output_image_path, base_graph_name, image_format='png'):
    """
    Internal core function to build CFG object and render it using dot via build_visual.
    Includes a basic graphviz test for diagnostics.

    Raises exceptions on failure (e.g., SyntaxError, FileNotFoundError, RuntimeError).
    """
    # Step 1: Build the CFG object using py2cfg
    logger.info(f"Building CFG object for '{os.path.basename(input_py_path)}'")
    from py2cfg import CFGBuilder  # Ensure import is available
    try:
        cfg = CFGBuilder().build_from_file(base_graph_name, input_py_path)
        logger.info("CFG object created.")
    except SyntaxError as syn_err:
        logger.error(f"Syntax error in input file '{input_py_path}': {syn_err}")
        err_details = f"{syn_err}"
        if hasattr(syn_err, 'lineno') and syn_err.lineno:
             err_details += f" (line {syn_err.lineno})"
        raise RuntimeError(f"Input file contains syntax errors: {err_details}") from syn_err
    except Exception as build_err:
        logger.error(f"Failed during CFGBuilder().build_from_file: {build_err}", exc_info=True)
        raise RuntimeError(f"Failed to build CFG object: {build_err}") from build_err

    # Step 2: Basic check if cfg object was created
    if not cfg:
        logger.error("CFGBuilder().build_from_file returned None or invalid object.")
        raise RuntimeError("Failed to create a valid CFG object.")

    # --- Step 2.5: Basic Graphviz/Dot Sanity Check ---
    basic_test_passed = False
    logger.info("Running a basic graphviz/dot rendering test...")
    try:
        simple_dot = graphviz.Digraph('simple_test', comment='Basic Test')
        simple_dot.node('A', 'Hello')
        simple_dot.node('B', 'Graphviz')
        simple_dot.edge('A', 'B', label='Test Edge')
        # Use a distinct name for the test output in the same temp directory
        test_output_path = os.path.join(os.path.dirname(output_image_path), 'basic_test.png')
        # Use render method which is similar to what build_visual might use
        simple_dot.render(outfile=test_output_path, format=image_format, view=False, cleanup=True) # cleanup=True removes intermediate .gv file

        if os.path.exists(test_output_path) and os.path.getsize(test_output_path) > 0:
             logger.info(f"Basic graphviz test SUCCEEDED. Output at {test_output_path}")
             basic_test_passed = True
             # Clean up the test file if successful
             try:
                 os.remove(test_output_path)
                 # Also remove the .gv file if cleanup didn't get it
                 gv_test_file = os.path.splitext(test_output_path)[0]
                 if os.path.exists(gv_test_file):
                    os.remove(gv_test_file)
             except OSError:
                 logger.warning(f"Could not remove basic test file {test_output_path}")
        else:
             logger.error(f"Basic graphviz test FAILED. No valid output file created at {test_output_path}.")
             # If this basic test fails, 'dot' or its dependencies are likely broken
             raise RuntimeError("Basic graphviz test failed - 'dot' installation or dependencies might be broken.")

    except (subprocess.CalledProcessError, FileNotFoundError) as test_pipe_err:
        # Catch specific errors if render() uses pipe() internally and fails
        logger.error(f"Basic graphviz test FAILED during subprocess execution: {test_pipe_err}", exc_info=True)
        stderr_output = getattr(test_pipe_err, 'stderr', None)
        if isinstance(stderr_output, bytes):
             stderr_output = stderr_output.decode('utf-8', errors='replace')
        else:
             stderr_output = "N/A"
        raise RuntimeError(f"Basic graphviz test failed ('dot' command error). Stderr: {stderr_output}") from test_pipe_err
    except Exception as test_exc:
        # Catch any other exception during the basic test
        logger.error(f"Basic graphviz test FAILED with exception: {test_exc}", exc_info=True)
        raise RuntimeError(f"Basic graphviz test failed: {test_exc}") from test_exc
    # --- End Basic Test ---


    # Step 3: Attempt visualization directly using build_visual (only if basic test passed)
    # No need to proceed if the basic test already failed
    logger.info(f"Attempting visualization via build_visual() to '{output_image_path}'")
    try:
        cfg.build_visual(output_image_path, format=image_format, show=False)
        logger.info("build_visual() completed.")

    except FileNotFoundError as fnf_err:
        logger.error(f"'dot' command not found by build_visual: {fnf_err}", exc_info=True)
        raise RuntimeError(f"Graphviz 'dot' command not found by build_visual.") from fnf_err
    except AttributeError as attr_err:
         logger.error(f"AttributeError during build_visual(), likely invalid CFG state: {attr_err}", exc_info=True)
         raise RuntimeError(f"Failed visualization due to invalid CFG state: {attr_err}") from attr_err
    except Exception as visual_err:
        logger.error(f"Error during build_visual(): {visual_err}", exc_info=True)
        raise RuntimeError(f"Error occurred during CFG visualization: {visual_err}") from visual_err

    # Step 4: Check if the output file was actually created and is non-empty
    if not os.path.exists(output_image_path) or os.path.getsize(output_image_path) == 0:
        logger.error(f"build_visual() completed but output file is invalid: {output_image_path}")
        dot_runtime_path = shutil.which("dot")
        msg = "CFG visualization failed: Output invalid ('dot' failed silently or CFG was empty?)."
        if not dot_runtime_path:
             msg = "CFG visualization failed: Output invalid AND 'dot' command not found."
        elif basic_test_passed:
             # If basic test passed, implies issue is specific to py2cfg interaction
             msg += " (Note: Basic graphviz test passed, issue likely with py2cfg data/interaction)."
        # No need for specific warning about dot path here if already logged in basic test
        raise RuntimeError(msg)

    logger.info(f"Successfully generated CFG image: '{output_image_path}'")


# --- Web Application Interface ---

def generate_cfg_web(input_file_path, output_filename, format='png'):
    """
    Generate a CFG for web app use. Creates a temp dir for output.
    Manages exceptions and cleans up temp dir on error.

    Returns: Absolute path to the generated CFG image in its temp directory.
    """
    logger.info(f"generate_cfg_web called for: {os.path.basename(input_file_path)}")
    output_dir = None  # Initialize for cleanup block

    # Basic Input Validation
    if not os.path.exists(input_file_path):
         raise FileNotFoundError(f"Input file not found at: {input_file_path}")
    if not input_file_path.endswith('.py'):
        raise ValueError("Input must be a Python file (.py).")

    try:
        # Create a unique temporary directory for this output file
        output_dir = tempfile.mkdtemp()
        output_path = os.path.join(output_dir, output_filename)
        base_graph_name = output_filename.split('.')[0] # Use filename base for graph name

        # Call the core generation function
        _generate_and_visualize_cfg(input_file_path, output_path, base_graph_name, format)

        # If core function succeeded, return the path
        return output_path

    except Exception as e:
        # Catch any exception from the core function or earlier steps
        logger.error(f"Error in generate_cfg_web: {e}", exc_info=True)

        # Attempt cleanup of the output directory if it was created
        if output_dir and os.path.exists(output_dir):
            try:
                shutil.rmtree(output_dir)
                logger.info(f"Cleaned up temporary output directory '{output_dir}' after error.")
            except Exception as cleanup_e:
                logger.error(f"Failed to cleanup temporary output directory '{output_dir}': {cleanup_e}")

        # Re-raise the error. The core function raises informative RuntimeErrors.
        raise e


# --- Command-Line Interface ---

def main():
    """Parse command-line arguments and run the CFG generator."""
    parser = argparse.ArgumentParser(
        description="Generate a control flow graph (CFG) from a Python file.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    parser.add_argument(
        "input_file",
        help="Path to the input Python file (.py)."
    )
    parser.add_argument(
        "output_file",
        help="Path to the output image file (e.g., cfg.png)."
    )
    parser.add_argument(
        "--format",
        default="png",
        choices=['png', 'svg', 'pdf'],
        help="Output image format."
    )
    args = parser.parse_args()
    logger.info(f"CLI mode: Generating CFG for '{args.input_file}' -> '{args.output_file}' (format: {args.format})")

    # Ensure output directory exists for CLI usage
    output_dir_name = os.path.dirname(args.output_file)
    if output_dir_name == '':
        output_dir_name = '.' # Handle saving in current directory

    # Check existence *before* trying to create, avoid error if '.'
    if output_dir_name != '.' and not os.path.exists(output_dir_name):
        try:
            os.makedirs(output_dir_name)
            logger.info(f"Created output directory: '{output_dir_name}'")
        except OSError as makedir_err:
            print(f"Error: Cannot create output directory '{output_dir_name}': {makedir_err}")
            exit(1) # Exit CLI on directory creation failure

    try:
        # Call the core generation function
        base_graph_name = os.path.basename(args.output_file).split('.')[0]
        _generate_and_visualize_cfg(args.input_file, args.output_file, base_graph_name, args.format)
        print(f"CFG generated successfully: '{args.output_file}'")

    # Catch specific exceptions first for potentially better CLI messages
    except FileNotFoundError as fnf:
         print(f"Error: Input file not found - {fnf}")
         logger.error(f"CLI Error: {fnf}", exc_info=True)
         exit(1)
    except ValueError as ve: # Catches invalid .py extension
        print(f"Error: {ve}")
        logger.error(f"CLI Error: {ve}", exc_info=True)
        exit(1)
    except RuntimeError as rte: # Catches errors raised by _generate_and_visualize_cfg
        print(f"Error: {rte}")
        logger.error(f"CLI Error: {rte}", exc_info=True)
        exit(1)
    except ImportError as ie: # Should not happen if installed, but good practice
        print(f"Error: Internal dependency missing - {ie}")
        logger.error(f"CLI Error: {ie}", exc_info=True)
        exit(1)
    except Exception as e:
        # Catch any other unexpected errors
        print(f"An unexpected error occurred: {e}")
        logger.error(f"Unexpected CLI Error: {e}", exc_info=True)
        exit(1)

if __name__ == "__main__":
    # This try-except block ensures necessary libraries are available when run as a script
    try:
         # Check essential imports
         from py2cfg import CFGBuilder
         import graphviz # Needed for the basic test
         main()
    except ImportError as import_err:
         print(f"Error: Missing required library - {import_err}. Please ensure all dependencies in requirements.txt are installed.")
         logging.error(f"ImportError on script execution: {import_err}")
         exit(1)
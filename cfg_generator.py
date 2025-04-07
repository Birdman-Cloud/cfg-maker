# cfg_generator.py
import argparse
import os
import tempfile
import logging
import subprocess # Still potentially needed if graphviz library uses it indirectly
import shutil    # Needed for cleanup

# --- Configuration ---
# Configure basic logging (using a more detailed format for better debugging)
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(name)s - %(message)s')
logger = logging.getLogger(__name__) # Use a specific logger

# --- Core Generation Logic ---

def _generate_and_visualize_cfg(input_py_path, output_image_path, base_graph_name, image_format='png'):
    """
    Internal core function to build CFG object and render it using dot via build_visual.

    Raises exceptions on failure (e.g., SyntaxError, FileNotFoundError, RuntimeError).
    """
    # Step 1: Build the CFG object using py2cfg
    logger.info(f"Building CFG object for '{os.path.basename(input_py_path)}'")
    # Ensure py2cfg is imported correctly
    # If using globally, ensure it's available when file is imported
    from py2cfg import CFGBuilder
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

    # Step 3: Attempt visualization directly using build_visual
    logger.info(f"Attempting visualization via build_visual() to '{output_image_path}'")
    try:
        # Let build_visual handle internal graph creation and dot execution
        cfg.build_visual(output_image_path, format=image_format, show=False)
        logger.info("build_visual() completed.")

    except FileNotFoundError as fnf_err:
        # Catch if build_visual itself can't find 'dot'
        logger.error(f"'dot' command not found by build_visual: {fnf_err}", exc_info=True)
        raise RuntimeError(f"Graphviz 'dot' command not found by build_visual.") from fnf_err
    # Catching AttributeError which might occur if cfg object is malformed for build_visual
    except AttributeError as attr_err:
         logger.error(f"AttributeError during build_visual(), likely invalid CFG state: {attr_err}", exc_info=True)
         raise RuntimeError(f"Failed visualization due to invalid CFG state: {attr_err}") from attr_err
    except Exception as visual_err:
        # Catch other potential errors during visualization
        logger.error(f"Error during build_visual(): {visual_err}", exc_info=True)
        raise RuntimeError(f"Error occurred during CFG visualization: {visual_err}") from visual_err

    # Step 4: Check if the output file was actually created and is non-empty
    # This remains the crucial check for success
    if not os.path.exists(output_image_path) or os.path.getsize(output_image_path) == 0:
        logger.error(f"build_visual() completed but output file is invalid: {output_image_path}")
        # Check dot path again at point of failure for extra context
        dot_runtime_path = shutil.which("dot")
        if not dot_runtime_path:
             logger.error("'dot' command not found via shutil.which() at runtime.")
             raise RuntimeError("CFG visualization failed: Output invalid AND 'dot' command not found.")
        else:
             logger.warning(f"'dot' found at {dot_runtime_path}, but build_visual() produced invalid output.")
             raise RuntimeError("CFG visualization failed: Output invalid ('dot' failed silently or CFG was empty?).")

    logger.info(f"Successfully generated CFG image: '{output_image_path}'")
    # No explicit return needed here; success means the file was created.


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
    # Handle case where output_file has no directory part (save in current dir)
    if output_dir_name == '':
        output_dir_name = '.'

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
    # This try-except block ensures py2cfg is available when run as a script
    try:
         from py2cfg import CFGBuilder # Check import availability
         main()
    except ImportError:
         print("Error: Missing 'py2cfg' library. Please install it (`pip install py2cfg==0.7.3`).")
         logging.error("ImportError for py2cfg. Ensure it's in requirements.txt and installed.")
         exit(1)
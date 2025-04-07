# cfg_generator.py
import argparse
import os
import tempfile
import logging
import subprocess # Needed for running dot via pipe
import shutil    # Needed for cleanup

# --- Configuration ---
# Configure basic logging (consider adding timestamps, etc., if needed)
# Using a more detailed format for better debugging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(name)s - %(message)s')
logger = logging.getLogger(__name__) # Use a specific logger

# --- Core Generation Logic ---

def _generate_and_visualize_cfg(input_py_path, output_image_path, base_graph_name, image_format='png'):
    """
    Internal core function to build CFG object and render it using dot.

    Raises exceptions on failure (e.g., SyntaxError, FileNotFoundError, RuntimeError).
    """
    # Step 1: Build the CFG object using py2cfg
    logger.info(f"Building CFG object for '{os.path.basename(input_py_path)}'")
    # Ensure py2cfg is imported correctly within the scope where CFGBuilder is needed
    from py2cfg import CFGBuilder
    try:
        cfg = CFGBuilder().build_from_file(base_graph_name, input_py_path)
        logger.info("CFG object created.")
    except SyntaxError as syn_err:
        logger.error(f"Syntax error in input file '{input_py_path}': {syn_err}")
        # Include line number if available
        err_details = f"{syn_err}"
        if hasattr(syn_err, 'lineno') and syn_err.lineno:
             err_details += f" (line {syn_err.lineno})"
        raise RuntimeError(f"Input file contains syntax errors: {err_details}") from syn_err
    # Catch potential errors from py2cfg apart from SyntaxError
    except Exception as build_err:
        logger.error(f"Failed during CFGBuilder().build_from_file: {build_err}", exc_info=True)
        raise RuntimeError(f"Failed to build CFG object: {build_err}") from build_err

    # Step 2: Check if the core graph attribute exists
    if not cfg or not hasattr(cfg, 'graph') or not cfg.graph:
        logger.error("Failed to create a valid CFG graph object from the input (cfg or cfg.graph is invalid).")
        raise RuntimeError("Failed to create a valid CFG graph object (empty or unparsable input?).")

    # Step 3: Attempt visualization using graphviz.pipe to capture output/errors
    logger.info(f"Attempting to visualize graph via pipe (format: {image_format}) to '{output_image_path}'")
    img_output_bytes = None
    try:
        # The cfg.graph object should be a graphviz.Digraph
        # Use pipe() to execute 'dot' and get the raw output bytes
        img_output_bytes = cfg.graph.pipe(format=image_format) # Returns bytes
        logger.info(f"Graphviz pipe() returned {len(img_output_bytes)} bytes.")

    except (subprocess.CalledProcessError, FileNotFoundError) as pipe_err:
        logger.error(f"'dot' command execution failed during pipe(): {pipe_err}", exc_info=True)
        # Attempt to decode stderr for better logging
        stderr_output = getattr(pipe_err, 'stderr', None)
        if isinstance(stderr_output, bytes):
             stderr_output = stderr_output.decode('utf-8', errors='replace')
        else:
             stderr_output = "N/A"
        raise RuntimeError(f"Graphviz 'dot' command failed. Stderr: {stderr_output}") from pipe_err
    except Exception as pipe_exc:
        logger.error(f"Unexpected error during graphviz pipe(): {pipe_exc}", exc_info=True)
        raise RuntimeError(f"Unexpected error during graphviz pipe(): {pipe_exc}") from pipe_exc

    # Step 4: Check if pipe output is valid and write to file
    if not img_output_bytes:
        logger.error("Graphviz pipe() returned no output.")
        raise RuntimeError("Graphviz 'dot' command ran but returned empty output.")

    try:
        with open(output_image_path, 'wb') as f:
            f.write(img_output_bytes)
        logger.info(f"Successfully wrote {len(img_output_bytes)} bytes to {output_image_path}")
    except OSError as write_err:
        logger.error(f"Failed to write pipe output to file {output_image_path}: {write_err}", exc_info=True)
        raise RuntimeError(f"Failed to write CFG image to disk: {write_err}") from write_err

    # Step 5: Final check on the written file
    if not os.path.exists(output_image_path) or os.path.getsize(output_image_path) == 0:
        logger.error(f"Output file check failed after write! Path: {output_image_path}")
        raise RuntimeError(f"CFG visualization failed. Output file empty or missing after write.")

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
    # ... (parser arguments remain the same) ...
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

    if not os.path.exists(output_dir_name):
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
    except ValueError as ve: # Catches invalid .py extension from core function if passed directly
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
    # Make sure py2cfg import happens here if needed, or handle potential NameError
    try:
         # Import CFGBuilder here if it's only needed when run as script
         # This avoids potential import errors if the file is just imported as a module
         # Correction: It's needed in _generate_and_visualize_cfg, so import must be global or passed in.
         # Let's keep the global import but make sure requirements are met.
         from py2cfg import CFGBuilder
         main()
    except ImportError:
         print("Error: Missing 'py2cfg' library. Please install it (`pip install py2cfg`).")
         exit(1)
    except NameError as ne:
         # Catch if CFGBuilder wasn't imported due to some issue.
         print(f"Error: NameError encountered - {ne}. Is 'py2cfg' installed correctly?")
         exit(1)
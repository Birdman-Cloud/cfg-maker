# cfg_generator.py
import argparse
import os
from py2cfg import CFGBuilder
import tempfile
import logging # Added for better error insights

# Configure basic logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def generate_cfg_web(input_file_path, output_filename, format='png'):
    """
    Generate a control flow graph (CFG) from a Python file and save it as an image.

    Args:
        input_file_path (str): Absolute path to the uploaded Python file in a temporary location.
        output_filename (str): Desired base name for the output image file (e.g., 'cfg.png').
        format (str): Output format (e.g., 'png', 'svg', 'pdf'). Default is 'png'.

    Returns:
        str: Absolute path to the generated CFG image in a new temporary directory.

    Raises:
        ValueError: If the input file is not a Python file.
        RuntimeError: If CFG generation fails (e.g., empty CFG, dot executable issue).
    """
    logging.info(f"Starting CFG generation for: {os.path.basename(input_file_path)}")
    # Validate input file path existence
    if not os.path.exists(input_file_path):
         raise FileNotFoundError(f"Input file not found at: {input_file_path}")
    if not input_file_path.endswith('.py'):
        raise ValueError("Input must be a Python file (.py).")

    # Create a *new* temporary directory specifically for this output file
    # This helps manage cleanup and isolation.
    output_dir = tempfile.mkdtemp()
    output_path = os.path.join(output_dir, output_filename)
    logging.info(f"Output will be saved to: {output_path}")

    # Generate and visualize the CFG
    try:
        cfg = CFGBuilder().build_from_file(output_filename.split('.')[0], input_file_path)
        # Corrected check:
        if not cfg or not cfg.graph: # Check if the CFG object or its graph attribute is invalid
            logging.warning(f"Generated CFG object or its graph attribute is invalid for '{os.path.basename(input_file_path)}'. Input might be empty or unparsable.")
            raise RuntimeError("Generated CFG is empty or invalid. Input file might lack executable code or be unparsable.")

        logging.info(f"CFG object created. Attempting to build visual: {output_path} (format: {format})")
        # The build_visual method requires the 'dot' command from Graphviz
        cfg.build_visual(output_path, format=format, show=False) # Ensure show=False for server environment

        # Check if the output file was actually created
        if not os.path.exists(output_path) or os.path.getsize(output_path) == 0:
             logging.error(f"CFG visualization failed. Output file not created or empty: {output_path}")
             raise RuntimeError(f"CFG visualization failed. 'dot' command might be missing or failed. Check Graphviz installation and PATH.")

        logging.info(f"CFG image successfully generated: {output_path}")
        return output_path

    except ImportError as ie:
         logging.error(f"ImportError during CFG generation: {ie}. Is 'py2cfg' installed correctly?")
         raise RuntimeError(f"Internal dependency error: {ie}")
    except Exception as e:
        # Catch any other unexpected errors during CFG building or visualization
        logging.error(f"An unexpected error occurred during CFG generation: {e}", exc_info=True) # Log traceback
        # Attempt cleanup of the output directory if creation failed partway
        if os.path.exists(output_dir):
            try:
                import shutil
                shutil.rmtree(output_dir)
            except Exception as cleanup_e:
                 logging.error(f"Failed to cleanup temporary output directory '{output_dir}': {cleanup_e}")
        raise RuntimeError(f"Failed to generate or visualize CFG: {e}")

# Keep the main block if you want to use it as a CLI tool sometimes
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

    # Note: This CLI part doesn't use the web-focused temp dir logic directly
    # It saves directly to the specified output_file path.
    temp_input_dir = tempfile.mkdtemp()
    cli_input_path = os.path.join(temp_input_dir, os.path.basename(args.input_file))
    # For CLI, we might need to copy the file if it's not already accessible
    # Or adjust generate_cfg_web to handle direct paths vs temp paths differently.
    # For simplicity here, assume args.input_file is accessible. Let's call the core logic.

    output_base_name = os.path.basename(args.output_file)
    output_dir_name = os.path.dirname(args.output_file)

    if not output_dir_name:
        output_dir_name = "." # Save in current dir if no path specified

    os.makedirs(output_dir_name, exist_ok=True) # Ensure output dir exists

    try:
        # This CLI part doesn't fit generate_cfg_web's temporary directory model well.
        # Re-implementing the core CFGBuilder logic here for CLI use:
        cfg = CFGBuilder().build_from_file(output_base_name.split('.')[0], args.input_file)
        if not cfg or not cfg.graph:
            raise RuntimeError("Generated CFG is empty. The input file may contain no executable code.")
        cfg.build_visual(args.output_file, format=args.format, show=False)
        print(f"CFG generated successfully: '{args.output_file}'")

    except (FileNotFoundError, ValueError, SyntaxError, RuntimeError, ImportError) as e:
        print(f"Error: {e}")
        exit(1)
    finally:
        # Clean up temp input dir if we used one
        import shutil
        shutil.rmtree(temp_input_dir, ignore_errors=True)


if __name__ == "__main__":
    main()
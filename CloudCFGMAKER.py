import argparse
import os
from py2cfg import CFGBuilder
import tempfile

def generate_cfg_web(input_file, output_file, format='png'):
    """
    Generate a control flow graph (CFG) from a Python file and save it as an image in a web context.

    Args:
        input_file (str): Path to the uploaded Python file.
        output_file (str): Name of the output image file (e.g., 'cfg.png').
        format (str): Output format (e.g., 'png', 'svg', 'pdf'). Default is 'png'.

    Returns:
        str: Path to the generated CFG image.

    Raises:
        ValueError: If the input file is not a Python file.
        RuntimeError: If CFG generation fails.
    """
    # Validate input file
    if not input_file.endswith('.py'):
        raise ValueError("Input must be a Python file (.py).")

    # Use a temporary directory for output
    output_dir = tempfile.mkdtemp()
    output_path = os.path.join(output_dir, output_file)

    # Generate and visualize the CFG
    try:
        cfg = CFGBuilder().build_from_file('cfg', input_file)
        if not cfg:
            raise RuntimeError("Generated CFG is empty. The input file may contain no executable code.")
        cfg.build_visual(output_path, format)
        return output_path
    except Exception as e:
        raise RuntimeError(f"Failed to generate CFG: {e}")

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

    try:
        generate_cfg_web(args.input_file, args.output_file, args.format)
        print(f"CFG generated successfully: '{args.output_file}'")
    except (FileNotFoundError, ValueError, SyntaxError, RuntimeError) as e:
        print(f"Error: {e}")
        exit(1)

if __name__ == "__main__":
    main()
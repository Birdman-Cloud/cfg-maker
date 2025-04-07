# cfggenerator.py
# --- At the top of cfggenerator.py ---
import os
import logging
import tempfile
from py2cfg import CFGBuilder
# Only import cc_visit now
from radon.complexity import cc_visit
# We no longer need to import radon.complexity itself or SCORE

import math # Needed for infinity

# Configure logging FIRST
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# --- Define the complexity ranking thresholds directly ---
# Based on Radon's default SCORE values
_COMPLEXITY_RANK_THRESHOLDS = (
    # (lower_bound, upper_bound, rank_letter) - Use upper bound for <= check
    (1, 5, 'A'),
    (6, 10, 'B'),
    (11, 20, 'C'),
    (21, 30, 'D'),
    (31, 40, 'E'),
    (41, math.inf, 'F'), # Use math.inf for the last upper bound
)
print("DEBUG cfggenerator.py: Using hardcoded complexity thresholds.", flush=True)

def annotate_execution_order(cfg):
    """
    Annotate the CFG with execution order numbers on nodes (BFS).
    """
    if not hasattr(cfg, 'entry') or cfg.entry is None:
        logging.warning("CFG object missing 'entry' node or entry is None. Skipping execution order.")
        return

    order = 1
    if cfg.entry:
        queue = [cfg.entry]
    else:
        logging.warning("CFG entry node is None, cannot perform BFS for annotation.")
        return
        
    visited = set()

    while queue:
        node = queue.pop(0)
        if node in visited:
            continue
        visited.add(node)

        try:
            current_label = getattr(node, 'label', None)
            if isinstance(current_label, str):
                 node.label = f"{order}. {current_label}"
            else:
                 logging.debug(f"Node {getattr(node, 'id', 'N/A')} has non-string label: {type(current_label)}. Skipping order prefix.")
                 pass
        except AttributeError:
            logging.warning(f"Could not set label for node {getattr(node, 'id', 'N/A')}. Skipping annotation for this node.")
            pass

        order += 1

        successors = getattr(node, 'successors', [])
        if isinstance(successors, (list, tuple, set)):
             for succ in successors:
                 if succ is not None and succ not in visited:
                     queue.append(succ)
        else:
             logging.warning(f"Node {getattr(node, 'id', 'N/A')} successors attribute is not iterable: {type(successors)}")


def calculate_cyclomatic_complexity(filepath):
    """
    Compute cyclomatic complexity using radon.
    Args:
        filepath (str): Path to the Python file.
    Returns:
        list: A list of strings describing complexity, or an error message string.
        int: Total complexity score across all blocks.
    """
    print(f"DEBUG calc_complexity: Entry.", flush=True) # Keep this debug line
    results = []
    total_complexity = 0
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            code = f.read()
        if not code.strip():
            return ["Source file is empty."], 0

        try:
             blocks = cc_visit(code)
        except Exception as visit_e:
             logging.error(f"Error during radon's cc_visit: {visit_e}")
             return [f"Error parsing code for complexity: {visit_e}"], 0
             
        if not blocks:
            results.append("No functions or methods found for complexity analysis.")
        else:
            # --- Use the hardcoded thresholds ---
            print(f"DEBUG calc_complexity: Calculating ranks using hardcoded thresholds.", flush=True)
            for block in blocks:
                rank = 'F' # Default to highest complexity rank if not found (or 'A' if preferred)
                try:
                    # Iterate through our hardcoded thresholds
                    for _lower, upper_bound, rank_letter in _COMPLEXITY_RANK_THRESHOLDS:
                        # Check if block complexity is less than or equal to the upper bound
                        if block.complexity <= upper_bound:
                            rank = rank_letter
                            break # Found the rank, exit inner loop
                except Exception as e_rank:
                    logging.error(f"Error calculating rank for complexity {block.complexity}: {e_rank}")
                    rank = '?' # Indicate error in rank calculation

                results.append(
                    f"- {block.classname or ''}{block.name} ({block.lineno}-{block.endline}): "
                    f"Complexity {block.complexity} ({rank})"
                )
                total_complexity += block.complexity
        return results, total_complexity

    except ImportError:
        logging.error("Radon library might be missing or failed during cc_visit.")
        return ["Error: Radon library issue during complexity analysis."], 0
    except SyntaxError as e:
        logging.error(f"Syntax error during complexity analysis: {e}")
        return [f"Syntax Error in code: {e}"], 0
    except Exception as e:
        logging.error(f"Error during complexity analysis setup: {e}", exc_info=True)
        return [f"Error during complexity analysis: {e}"], 0


def generate_cfg_image(input_filepath, output_image_path, fmt='png'):
    """
    Generates a CFG image from a Python file.
    Args:
        input_filepath (str): Path to the input Python file.
        output_image_path (str): Full path where the output image should be saved.
        fmt (str): Output format ('png', 'svg', 'pdf').
    Returns:
        str: Path to the generated image if successful, None otherwise.
    Raises:
        SyntaxError: If the input file has syntax errors.
        RuntimeError: For other CFG generation errors.
        Exception: For unexpected errors.
    """
    try:
        output_dir = os.path.dirname(output_image_path)
        os.makedirs(output_dir, exist_ok=True)
        logging.info(f"Ensured output directory exists: {output_dir}")

        try:
            cfg = CFGBuilder().build_from_file('cfg_analysis', input_filepath)
        except SyntaxError as e_build:
             logging.error(f"Syntax error during CFGBuilder().build_from_file: {e_build}")
             raise
        except Exception as e_build:
             logging.error(f"Error during CFGBuilder().build_from_file: {e_build}", exc_info=True)
             raise RuntimeError(f"Failed during CFG building step: {e_build}")

        if not cfg or not hasattr(cfg, 'entry') or cfg.entry is None:
            with open(input_filepath, 'r', encoding='utf-8') as f:
                if not f.read().strip():
                    logging.error("Input file is empty.")
                    raise RuntimeError("Input file is empty.")
            logging.warning(f"CFG generated for '{os.path.basename(input_filepath)}' is empty or has no entry point. Rendering might be minimal or fail.")

        try:
            annotate_execution_order(cfg)
        except Exception as annotate_e:
            logging.warning(f"Could not fully annotate CFG: {annotate_e}", exc_info=True)

        logging.info(f"Attempting to build visual CFG at: {output_image_path}")
        try:
             cfg.build_visual(output_image_path, format=fmt, show=False)
             logging.info(f"CFG image generated successfully: {output_image_path}")
             return output_image_path
        except Exception as e_visual:
             logging.error(f"Error during cfg.build_visual: {e_visual}", exc_info=True)
             if "failed to execute" in str(e_visual).lower() or "command not found" in str(e_visual).lower():
                 raise RuntimeError("Server configuration error: Graphviz executable not found or failed.")
             else:
                 raise RuntimeError(f"Failed to visualize CFG: {e_visual}")

    except FileNotFoundError:
        logging.error(f"Input file disappeared: {input_filepath}", exc_info=True)
        raise RuntimeError(f"Internal Server Error: Could not find temporary file.")
    except SyntaxError as e:
        logging.error(f"Syntax error in input file '{os.path.basename(input_filepath)}': {e}")
        raise SyntaxError(f"Syntax error in uploaded file: {e}")
    except ImportError as e:
        logging.error(f"Import Error during CFG generation (likely graphviz Python wrapper): {e}", exc_info=True)
        raise RuntimeError("Server configuration error: Graphviz Python library might be missing.")
    except RuntimeError as e:
         logging.error(f"Runtime error during CFG generation: {e}", exc_info=True)
         raise
    except Exception as e:
        logging.error(f"Unexpected error generating CFG for '{os.path.basename(input_filepath)}': {e}", exc_info=True)
        raise RuntimeError(f"Unexpected error generating CFG image: {e}")
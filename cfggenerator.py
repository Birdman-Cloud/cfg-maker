# cfggenerator.py
# --- At the top of cfggenerator.py ---
import os
import logging
import tempfile
from py2cfg import CFGBuilder
# Only import cc_visit now, we will get SCORE directly later
from radon.complexity import cc_visit 
import radon.complexity # Import the module itself for direct access later

# Configure logging FIRST (good practice)
# Ensure level is appropriate (INFO captures info, warning, error; DEBUG captures more)
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
# Add a debug print to confirm module import
print(f"DEBUG cfggenerator.py: Initial import complete. Type of radon.complexity module: {type(radon.complexity)}", flush=True)

def annotate_execution_order(cfg):
    """
    Annotate the CFG with execution order numbers on nodes (BFS).
    """
    if not hasattr(cfg, 'entry') or cfg.entry is None:
        logging.warning("CFG object missing 'entry' node or entry is None. Skipping execution order.")
        return

    order = 1
    # Check if entry node exists and has successors before starting BFS
    if cfg.entry:
        queue = [cfg.entry]
    else:
        logging.warning("CFG entry node is None, cannot perform BFS for annotation.")
        return # Cannot proceed without an entry node
        
    visited = set()

    while queue:
        node = queue.pop(0)
        if node in visited:
            continue
        visited.add(node)

        try:
            # Ensure label exists and is string before formatting
            current_label = getattr(node, 'label', None)
            if isinstance(current_label, str):
                 node.label = f"{order}. {current_label}"
            else:
                 # Handle nodes without string labels if necessary, maybe assign a default
                 # Or log if it's unexpected
                 # For now, we just won't prefix if label isn't a string
                 logging.debug(f"Node {getattr(node, 'id', 'N/A')} has non-string label: {type(current_label)}. Skipping order prefix.")
                 pass # Keep original non-string label or None
        except AttributeError:
            # This might happen if node objects don't support setting 'label'
            logging.warning(f"Could not set label for node {getattr(node, 'id', 'N/A')}. Skipping annotation for this node.")
            pass

        order += 1

        # Check successors exist and are iterable
        successors = getattr(node, 'successors', [])
        if isinstance(successors, (list, tuple, set)): # Check if it's an iterable collection
             for succ in successors:
                 # Ensure successor is not None before checking if visited
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
    # Add this print at the function start:
    print(f"DEBUG calc_complexity: Entry.", flush=True)
    results = []
    total_complexity = 0
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            code = f.read()
        if not code.strip():
            return ["Source file is empty."], 0

        # Perform complexity visit
        # Wrap this in try/except as well, as it parses the code
        try:
             blocks = cc_visit(code)
        except Exception as visit_e:
             logging.error(f"Error during radon's cc_visit: {visit_e}")
             # Add more specific error reporting if needed based on visit_e type
             return [f"Error parsing code for complexity: {visit_e}"], 0
             
        if not blocks:
            results.append("No functions or methods found for complexity analysis.")
        else:
            # --- Access SCORE directly inside the loop ---
            # Fetch the SCORE attribute from the module *safely* each time (or once before loop)
            # Using getattr is safer than direct access if attribute might be missing
            score_data = getattr(radon.complexity, 'SCORE', None) 
            score_data_type = type(score_data)
            print(f"DEBUG calc_complexity: Fetched radon.complexity.SCORE directly. Type: {score_data_type}", flush=True) # Add debug

            for block in blocks:
                rank = 'A' # Default Rank
                try:
                    # Check the type of the fetched score_data
                    if isinstance(score_data, (list, tuple)):
                        for score_entry in score_data:
                             if isinstance(score_entry, (list, tuple)) and len(score_entry) >= 2:
                                 score_limit = score_entry[0]
                                 current_rank = score_entry[1]
                                 # Ensure score_limit is comparable (e.g., int/float)
                                 if isinstance(score_limit, (int, float)) and block.complexity <= score_limit:
                                     rank = current_rank
                                     break
                             else:
                                 logging.warning(f"Unexpected item format in radon.complexity score data: {score_entry}")
                    else:
                         # Log the warning using the type we just fetched
                         logging.warning(f"radon.complexity.SCORE (accessed directly) is not a list or tuple: {score_data_type}")
                except Exception as e_rank:
                    logging.error(f"Error calculating rank for complexity {block.complexity}: {e_rank}")

                results.append(
                    f"- {block.classname or ''}{block.name} ({block.lineno}-{block.endline}): "
                    f"Complexity {block.complexity} ({rank})"
                )
                total_complexity += block.complexity
        return results, total_complexity

    # Keep specific exceptions for clarity
    except ImportError: 
        logging.error("Radon library might be missing or failed during cc_visit.")
        return ["Error: Radon library issue during complexity analysis."], 0
    except SyntaxError as e:
        logging.error(f"Syntax error during complexity analysis: {e}")
        return [f"Syntax Error in code: {e}"], 0
    except Exception as e:
        # Log general errors during file reading or other setup
        logging.error(f"Error during complexity analysis setup: {e}", exc_info=True) # Add exc_info for traceback
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
        # Ensure directory exists (makedirs handles potential race conditions better)
        os.makedirs(output_dir, exist_ok=True) 
        logging.info(f"Ensured output directory exists: {output_dir}")

        # Build CFG - Wrap in try/except as it parses code
        try:
            cfg = CFGBuilder().build_from_file('cfg_analysis', input_filepath)
        except SyntaxError as e_build: # Catch syntax errors during build specifically
             logging.error(f"Syntax error during CFGBuilder().build_from_file: {e_build}")
             raise # Re-raise SyntaxError to be caught by outer block correctly
        except Exception as e_build:
             logging.error(f"Error during CFGBuilder().build_from_file: {e_build}", exc_info=True)
             raise RuntimeError(f"Failed during CFG building step: {e_build}")


        if not cfg or not hasattr(cfg, 'entry') or cfg.entry is None:
            # Check file content *after* attempting build, as build might fail for non-empty files too
            with open(input_filepath, 'r', encoding='utf-8') as f:
                if not f.read().strip():
                    logging.error("Input file is empty.") # Log as error? Or just info?
                    # Decide if empty file should raise error or just return None/empty image
                    raise RuntimeError("Input file is empty.") 
            
            # If file wasn't empty, but CFG is bad, log warning
            logging.warning(f"CFG generated for '{os.path.basename(input_filepath)}' is empty or has no entry point. Rendering might be minimal or fail.")

        # Annotate nodes (best effort)
        try:
            annotate_execution_order(cfg)
        except Exception as annotate_e:
            # Log annotation errors but don't fail the image generation
            logging.warning(f"Could not fully annotate CFG: {annotate_e}", exc_info=True) 

        # Visualize and save
        logging.info(f"Attempting to build visual CFG at: {output_image_path}")
        try:
             # format vs fmt mismatch? build_visual uses 'format'
             cfg.build_visual(output_image_path, format=fmt, show=False) 
             logging.info(f"CFG image generated successfully: {output_image_path}")
             return output_image_path
        except Exception as e_visual:
             logging.error(f"Error during cfg.build_visual: {e_visual}", exc_info=True)
             # Check specifically for graphviz execution errors
             if "failed to execute" in str(e_visual).lower() or "command not found" in str(e_visual).lower():
                 raise RuntimeError("Server configuration error: Graphviz executable not found or failed.")
             else:
                 raise RuntimeError(f"Failed to visualize CFG: {e_visual}")


    # Keep outer exception handling
    except FileNotFoundError:
        logging.error(f"Input file disappeared: {input_filepath}", exc_info=True)
        raise RuntimeError(f"Internal Server Error: Could not find temporary file.")
    except SyntaxError as e: # Catch re-raised SyntaxError
        logging.error(f"Syntax error in input file '{os.path.basename(input_filepath)}': {e}")
        raise SyntaxError(f"Syntax error in uploaded file: {e}")
    except ImportError as e: # e.g. graphviz python wrapper missing
        logging.error(f"Import Error during CFG generation (likely graphviz Python wrapper): {e}", exc_info=True)
        raise RuntimeError("Server configuration error: Graphviz Python library might be missing.")
    except RuntimeError as e: # Catch RuntimeErrors raised explicitly above
         # Log the specific runtime error message we created
         logging.error(f"Runtime error during CFG generation: {e}", exc_info=True)
         raise # Re-raise to be handled by Flask app
    except Exception as e: # Catch any other unexpected errors
        logging.error(f"Unexpected error generating CFG for '{os.path.basename(input_filepath)}': {e}", exc_info=True)
        raise RuntimeError(f"Unexpected error generating CFG image: {e}")
import os
import logging
import tempfile
from py2cfg import CFGBuilder
from radon.complexity import cc_visit, SCORE

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')


def annotate_execution_order(cfg):
    """
    Annotate the CFG with execution order numbers on nodes (BFS).
    """
    if not hasattr(cfg, 'entry') or cfg.entry is None:
        logging.warning("CFG object missing 'entry' node or entry is None. Skipping execution order.")
        return

    order = 1
    queue = [cfg.entry]
    visited = set()

    while queue:
        node = queue.pop(0)
        if node in visited:
            continue
        visited.add(node)

        try:
            current_label = getattr(node, 'label', '')
            node.label = f"{order}. {current_label}"
        except AttributeError:
            logging.warning("Could not set label for a node. Skipping annotation for this node.")
            pass

        order += 1

        successors = getattr(node, 'successors', [])
        for succ in successors:
            if succ not in visited:
                queue.append(succ)


def calculate_cyclomatic_complexity(filepath):
    """
    Compute cyclomatic complexity using radon.
    Args:
        filepath (str): Path to the Python file.
    Returns:
        list: A list of strings describing complexity, or an error message string.
        int: Total complexity score across all blocks.
    """
    results = []
    total_complexity = 0
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            code = f.read()
        if not code.strip():
            return ["Source file is empty."], 0

        blocks = cc_visit(code)
        if not blocks:
            results.append("No functions or methods found for complexity analysis.")
        else:
            for block in blocks:
                # Determine rank based on complexity score
                rank = 'A'  # Default Rank
                try:
                    if isinstance(SCORE, (list, tuple)):
                        for score_entry in SCORE:
                            if isinstance(score_entry, (list, tuple)) and len(score_entry) >= 2:
                                score_limit = score_entry[0]
                                current_rank = score_entry[1]
                                if block.complexity <= score_limit:
                                    rank = current_rank
                                    break
                            else:
                                logging.warning(f"Unexpected item format in radon.complexity.SCORE: {score_entry}")
                    else:
                        logging.warning(f"radon.complexity.SCORE is not a list or tuple: {type(SCORE)}")
                except Exception as e_rank:
                    logging.error(f"Error calculating rank for complexity {block.complexity}: {e_rank}")

                results.append(
                    f"- {block.classname or ''}{block.name} ({block.lineno}-{block.endline}): "
                    f"Complexity {block.complexity} ({rank})"
                )
                total_complexity += block.complexity

        return results, total_complexity

    except ImportError:
        logging.error("Radon is not installed.")
        return ["Error: Radon library not found."], 0
    except SyntaxError as e:
        logging.error(f"Syntax error during complexity analysis: {e}")
        return [f"Syntax Error in code: {e}"], 0
    except Exception as e:
        logging.error(f"Error during complexity analysis: {e}")
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

        cfg = CFGBuilder().build_from_file('cfg_analysis', input_filepath)

        if not cfg or not hasattr(cfg, 'entry') or cfg.entry is None:
            with open(input_filepath, 'r', encoding='utf-8') as f:
                if not f.read().strip():
                    raise RuntimeError("Input file is empty.")

            logging.warning(f"CFG generated for '{input_filepath}' is empty or has no entry point. "
                            "Rendering might be minimal or fail.")

        try:
            annotate_execution_order(cfg)
        except Exception as annotate_e:
            logging.warning(f"Could not fully annotate CFG: {annotate_e}")

        logging.info(f"Attempting to build visual CFG at: {output_image_path}")
        cfg.build_visual(output_image_path, format=fmt, show=False)
        logging.info(f"CFG image generated successfully: {output_image_path}")
        return output_image_path

    except FileNotFoundError:
        logging.error(f"Input file not found: {input_filepath}")
        raise RuntimeError(f"Internal Server Error: Could not find temporary file.")
    except SyntaxError as e:
        logging.error(f"Syntax error in input file '{input_filepath}': {e}")
        raise SyntaxError(f"Syntax error in uploaded file: {e}")
    except ImportError as e:
        logging.error(f"Import Error during CFG generation (likely graphviz): {e}")
        raise RuntimeError("Server configuration error: Graphviz might be missing or not configured correctly.")
    except Exception as e:
        logging.error(f"Failed to generate or visualize CFG for '{input_filepath}': {e}")
        if "failed to execute" in str(e).lower() or "command not found" in str(e).lower():
            raise RuntimeError("Server configuration error: Graphviz executable not found. Please ensure it's installed.")
        else:
            raise RuntimeError(f"Failed to generate CFG image: {e}")

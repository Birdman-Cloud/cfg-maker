import os
import uuid
import logging
import tempfile
from flask import Flask, request, render_template, redirect, url_for, flash, send_from_directory
from werkzeug.utils import secure_filename
from cfggenerator import generate_cfg_image, calculate_cyclomatic_complexity

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Configuration
UPLOAD_FOLDER = tempfile.gettempdir() # Use system temp dir for uploads
STATIC_FOLDER = os.path.join(os.path.dirname(__file__), 'static')
GENERATED_IMAGES_FOLDER = os.path.join(STATIC_FOLDER, 'images')
ALLOWED_EXTENSIONS = {'py'}
MAX_CONTENT_LENGTH = 1 * 1024 * 1024  # 1 MB limit

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('FLASK_SECRET_KEY', 'a_default_dev_secret_key') # Use env var in production
app.config['MAX_CONTENT_LENGTH'] = MAX_CONTENT_LENGTH

# Ensure the generated images directory exists
os.makedirs(GENERATED_IMAGES_FOLDER, exist_ok=True)

def allowed_file(filename):
    """Checks if the file extension is allowed."""
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route('/', methods=['GET'])
def index():
    """Renders the main upload page."""
    return render_template('index.html')

@app.route('/upload', methods=['POST'])
def upload_file():
    """Handles file upload, generates CFG and complexity, shows results."""
    if 'python_file' not in request.files:
        flash('No file part in the request.')
        return redirect(url_for('index'))

    file = request.files['python_file']

    if file.filename == '':
        flash('No selected file.')
        return redirect(url_for('index'))

    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        # Use a temporary file to store the upload securely
        # Suffix is important for py2cfg/radon if they check extensions
        temp_suffix = f"_{filename}" if filename.endswith('.py') else '_upload.py'
        temp_input_file = None
        try:
            with tempfile.NamedTemporaryFile(mode='w+b', delete=False, dir=UPLOAD_FOLDER, suffix=temp_suffix) as temp_input_file:
                file.save(temp_input_file) # Save upload stream to temp file
                temp_input_filepath = temp_input_file.name # Get the path

            logging.info(f"File '{filename}' uploaded temporarily to '{temp_input_filepath}'")

            # Generate a unique name for the output image
            unique_id = uuid.uuid4()
            output_filename = f"cfg_{unique_id}.png"
            # Note: output_image_path is the *full* path for saving
            output_image_path = os.path.join(GENERATED_IMAGES_FOLDER, output_filename)
            # image_url_path is relative to the 'static' folder for use in HTML
            image_url_path = f"images/{output_filename}"

            complexity_results = []
            total_complexity = 0
            generated_image_path = None
            error_message = None

            try:
                # 1. Calculate Cyclomatic Complexity
                complexity_results, total_complexity = calculate_cyclomatic_complexity(temp_input_filepath)
                logging.info(f"Complexity calculated: {len(complexity_results)} blocks, Total={total_complexity}")

                # 2. Generate CFG Image
                generated_image_path = generate_cfg_image(temp_input_filepath, output_image_path, fmt='png')
                logging.info(f"CFG image generated: {generated_image_path}")

            except SyntaxError as e:
                error_message = f"Syntax Error: {e}"
                flash(error_message)
                logging.error(error_message)
            except RuntimeError as e:
                error_message = f"Error: {e}"
                flash(error_message)
                logging.error(error_message)
            except Exception as e:
                error_message = f"An unexpected error occurred: {e}"
                flash(error_message)
                logging.exception("Unexpected error during processing:") # Log stack trace

            # Clean up the temporary input file
            if temp_input_filepath and os.path.exists(temp_input_filepath):
                 os.remove(temp_input_filepath)
                 logging.info(f"Cleaned up temporary file: {temp_input_filepath}")


            if generated_image_path and not error_message:
                # Success - render results
                return render_template('results.html',
                                       image_file_url=image_url_path,
                                       complexity_results=complexity_results,
                                       total_complexity=total_complexity,
                                       original_filename=filename)
            else:
                # Failure or partial failure - redirect back to index
                # Flash message should already be set
                 # Clean up potentially generated (but unused) image file on error
                if output_image_path and os.path.exists(output_image_path) and not generated_image_path:
                    try:
                        os.remove(output_image_path)
                        logging.info(f"Cleaned up unused image file: {output_image_path}")
                    except OSError as rm_err:
                        logging.error(f"Error removing unused image file {output_image_path}: {rm_err}")
                return redirect(url_for('index'))

        except Exception as e:
             # Catch errors related to temp file creation or saving
             flash(f"Server error handling file upload: {e}")
             logging.exception("Error during file upload handling:")
             # Ensure cleanup even if temp file creation failed partially
             if temp_input_file and hasattr(temp_input_file, 'name') and os.path.exists(temp_input_file.name):
                 try:
                     os.remove(temp_input_file.name)
                 except OSError: pass # Ignore error during cleanup
             return redirect(url_for('index'))

    else:
        flash('Invalid file type. Please upload a .py file.')
        return redirect(url_for('index'))

# Serve static files (Flask does this automatically in debug, but good practice)
# This route is not strictly needed if using standard static folder config,
# but can be useful for serving generated images if they were outside 'static'
# @app.route('/generated/<filename>')
# def generated_file(filename):
#     return send_from_directory(GENERATED_IMAGES_FOLDER, filename)

# Error Handling
@app.errorhandler(404)
def not_found_error(error):
    return render_template('404.html'), 404 # You'll need to create templates/404.html

@app.errorhandler(500)
def internal_error(error):
    # Log the error details here if needed
    flash("An internal server error occurred. Please try again later.")
    return redirect(url_for('index')) # Redirect to index on 500

@app.errorhandler(413)
def request_entity_too_large(error):
    flash(f"File is too large. Maximum size is {MAX_CONTENT_LENGTH / 1024 / 1024:.1f} MB.")
    return redirect(url_for('index'))

if __name__ == '__main__':
    # Set a more specific host and port for local dev if needed
    # Use '0.0.0.0' to be accessible on the network
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 8080)), debug=False)
    # Note: When deploying with gunicorn, this __main__ block is NOT executed.
    # Gunicorn runs the 'app' object directly. debug=False is crucial for production.
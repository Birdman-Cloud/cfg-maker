# app.py
import os
import uuid
import logging
import tempfile
# Import send_from_directory
from flask import Flask, request, render_template, redirect, url_for, flash, send_from_directory 
from werkzeug.utils import secure_filename
# Assuming cfggenerator.py contains the updated logic
from cfggenerator import generate_cfg_image, calculate_cyclomatic_complexity

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Configuration
UPLOAD_FOLDER = tempfile.gettempdir() 
BASE_DIR = os.path.abspath(os.path.dirname(__file__))
STATIC_FOLDER_PATH = os.path.join(BASE_DIR, 'static')
GENERATED_IMAGES_FOLDER = os.path.join(STATIC_FOLDER_PATH, 'images') # Keep this definition
ALLOWED_EXTENSIONS = {'py'}
MAX_CONTENT_LENGTH = 1 * 1024 * 1024

# Use default static folder, or specify explicitly if you prefer
app = Flask(__name__) 
# Example if explicit: app = Flask(__name__, static_folder=STATIC_FOLDER_PATH)

app.config['SECRET_KEY'] = os.environ.get('FLASK_SECRET_KEY', 'a_default_dev_secret_key')
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

# --- NEW ROUTE for serving generated images ---
@app.route('/generated_images/<path:filename>')
def serve_generated_image(filename):
    """Serves an image file from the generated images folder."""
    logging.info(f"Attempting to serve image: {filename} from {GENERATED_IMAGES_FOLDER}")
    try:
        # Use send_from_directory for security and proper header handling
        return send_from_directory(GENERATED_IMAGES_FOLDER, filename)
    except FileNotFoundError:
        logging.error(f"Image not found: {os.path.join(GENERATED_IMAGES_FOLDER, filename)}")
        # You could return a default placeholder image or just abort with 404
        from flask import abort
        abort(404) 
    except Exception as e:
        logging.error(f"Error serving image {filename}: {e}", exc_info=True)
        from flask import abort
        abort(500) # Internal server error

# --- Existing /upload route ---
@app.route('/upload', methods=['POST'])
def upload_file():
    if 'python_file' not in request.files:
        flash('No file part in the request.')
        return redirect(url_for('index'))
    # ... (rest of file checking logic) ...

    file = request.files['python_file']
    if file.filename == '':
        flash('No selected file.')
        return redirect(url_for('index'))

    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        temp_suffix = f"_{filename}" if filename.endswith('.py') else '_upload.py'
        temp_input_filepath = None # Define outside try
        try:
            # Use NamedTemporaryFile correctly with context manager
            with tempfile.NamedTemporaryFile(mode='w+b', delete=False, dir=UPLOAD_FOLDER, suffix=temp_suffix) as temp_input_file:
                file.save(temp_input_file)
                temp_input_filepath = temp_input_file.name

            logging.info(f"File '{filename}' uploaded temporarily to '{temp_input_filepath}'")

            unique_id = uuid.uuid4()
            output_filename = f"cfg_{unique_id}.png"
            output_image_path = os.path.join(GENERATED_IMAGES_FOLDER, output_filename)
            
            # ** IMPORTANT: Change how we reference the image in the template **
            # We no longer use url_for('static'...) for the generated image.
            # We will use url_for('serve_generated_image'...) pointing to our new route.
            # image_url_path_for_template = f"images/{output_filename}" # OLD way for url_for('static'...)
            
            complexity_results = []
            total_complexity = 0
            generated_image_full_path = None # Store full path
            error_message = None

            try:
                complexity_results, total_complexity = calculate_cyclomatic_complexity(temp_input_filepath)
                logging.info(f"Complexity calculated: {len(complexity_results)} blocks, Total={total_complexity}")

                generated_image_full_path = generate_cfg_image(temp_input_filepath, output_image_path, fmt='png')
                logging.info(f"CFG image generated (full path): {generated_image_full_path}")

            # ... (rest of error handling: SyntaxError, RuntimeError, Exception) ...
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
                logging.exception("Unexpected error during processing:")


            # Clean up temp input file
            if temp_input_filepath and os.path.exists(temp_input_filepath):
                 os.remove(temp_input_filepath)
                 logging.info(f"Cleaned up temporary file: {temp_input_filepath}")

            # Check if generation succeeded before rendering results
            if generated_image_full_path and not error_message:
                # Pass only the filename to url_for for the new route
                image_filename_for_template = os.path.basename(generated_image_full_path) 
                logging.info(f"Rendering results with image filename: {image_filename_for_template}")
                return render_template('results.html',
                                       # Use the filename for the new route
                                       image_filename=image_filename_for_template, 
                                       complexity_results=complexity_results,
                                       total_complexity=total_complexity,
                                       original_filename=filename)
            else:
                 # Clean up potentially generated (but unused) image file on error
                if output_image_path and os.path.exists(output_image_path) and not generated_image_full_path:
                    try:
                        os.remove(output_image_path)
                        logging.info(f"Cleaned up unused image file: {output_image_path}")
                    except OSError as rm_err:
                        logging.error(f"Error removing unused image file {output_image_path}: {rm_err}")
                # Flash message should already be set if error_message exists
                if not error_message: # Handle cases where generation path is None without specific error
                    flash("Failed to generate CFG image.")
                return redirect(url_for('index'))

        # Catch errors related to temp file handling *outside* the inner try block
        except Exception as e_outer:
             flash(f"Server error handling file upload or processing: {e_outer}")
             logging.exception("Error during file upload/processing:")
             if temp_input_filepath and os.path.exists(temp_input_filepath):
                 try: os.remove(temp_input_filepath)
                 except OSError: pass
             return redirect(url_for('index'))

    else: # If file not allowed
        flash('Invalid file type. Please upload a .py file.')
        return redirect(url_for('index'))


# --- Error Handlers ---
@app.errorhandler(404)
def not_found_error(error):
    # Check if 404.html exists before rendering
    template_path = os.path.join(app.template_folder, '404.html')
    if os.path.exists(template_path):
        return render_template('404.html'), 404
    else:
        # Fallback if 404.html is missing
        return "<h1>404 - Not Found</h1><p>The requested resource was not found.</p>", 404

@app.errorhandler(500)
def internal_error(error):
    logging.exception("Internal Server Error:") # Log the actual error causing 500
    flash("An internal server error occurred. Please try again later.")
    return redirect(url_for('index'))

@app.errorhandler(413)
def request_entity_too_large(error):
    flash(f"File is too large. Maximum size is {app.config['MAX_CONTENT_LENGTH'] / 1024 / 1024:.1f} MB.")
    return redirect(url_for('index'))

if __name__ == '__main__':
    # Use PORT from environment variable provided by Render/Gunicorn
    port = int(os.environ.get('PORT', 8080)) 
    # Use 0.0.0.0 to be accessible externally (important for containers)
    # debug=False is crucial for production via Gunicorn
    app.run(host='0.0.0.0', port=port, debug=False)
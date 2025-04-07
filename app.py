from flask import Flask, request, render_template, send_from_directory, redirect, url_for, flash
import os
import tempfile
from flask_sqlalchemy import SQLAlchemy
import shutil
import logging
# Import the function from the overhauled generator
from cfg_generator import generate_cfg_web

# --- Basic Logging Setup ---
# Using a more detailed format and app-specific logger
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(name)s - %(message)s')
app_logger = logging.getLogger('flask.app') # Use Flask's standard logger name

# --- Graphviz Path Check ---
app_logger.info("🚀 Checking dot path at startup...")
dot_path = shutil.which("dot")
app_logger.info(f"System PATH: {os.environ.get('PATH')}")
app_logger.info(f"shutil.which('dot') found: {dot_path}")

# Ensure Graphviz's dot is in PATH
if not dot_path and "/usr/bin" not in os.environ["PATH"]:
    os.environ["PATH"] += os.pathsep + "/usr/bin"
    app_logger.info("Added /usr/bin to PATH")
if not dot_path and "/usr/local/bin" not in os.environ["PATH"]:
     os.environ["PATH"] += os.pathsep + "/usr/local/bin"
     app_logger.info("Added /usr/local/bin to PATH")

dot_path_after = shutil.which("dot")
app_logger.info(f"Dot path after potential PATH update: {dot_path_after}")
if not dot_path_after:
    app_logger.warning("Graphviz 'dot' command not found in PATH. CFG generation will likely fail.")

# --- Flask App Setup ---
app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'dev_secret_key_change_me')
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', 'sqlite:///site.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['MAX_CONTENT_LENGTH'] = 5 * 1024 * 1024 # 5MB limit

db = SQLAlchemy(app)

# --- Database Model (Commented Out) ---
# class Upload(db.Model):
#     id = db.Column(db.Integer, primary_key=True)
#     filename = db.Column(db.String(100), nullable=False)
#     # cfg_path = db.Column(db.String(200), nullable=False)

# with app.app_context():
#     # db.create_all()
#     pass

# --- Routes ---
@app.route('/', methods=['GET', 'POST'])
def upload_file():
    if request.method == 'POST':
        if 'file' not in request.files:
            flash("No file part in the request.", "error")
            return redirect(request.url)

        file = request.files['file']

        if file.filename == '':
            flash("No selected file.", "error")
            return redirect(request.url)

        if not file.filename.endswith('.py'):
            flash("Please upload a valid Python (.py) file.", "error")
            return redirect(request.url)

        input_temp_dir = None
        output_temp_dir = None
        try:
            # Save uploaded file
            input_temp_dir = tempfile.mkdtemp()
            input_path = os.path.join(input_temp_dir, file.filename)
            file.save(input_path)
            app_logger.info(f"Uploaded file saved temporarily to: {input_path}")

            # Generate CFG using the imported function (now uses staticfg internally)
            output_filename = 'cfg.png'
            cfg_image_path = generate_cfg_web(input_path, output_filename, format='png')

            # Get temporary directory details for serving the result
            output_temp_dir = os.path.dirname(cfg_image_path)
            image_name = os.path.basename(cfg_image_path)
            image_dir_basename = os.path.basename(output_temp_dir)

            app_logger.info(f"CFG generated, redirecting to result for image {image_name} in dir {image_dir_basename}")
            # Redirect to show result
            return redirect(url_for('show_result', image_dir=image_dir_basename, image_name=image_name))

        # --- Error Handling ---
        except FileNotFoundError as fnf:
             app_logger.error(f"File not found error during upload/processing: {fnf}", exc_info=True)
             flash(f"Error: {fnf}", "error")
             return redirect(request.url)
        except ValueError as ve:
             app_logger.error(f"Value error (e.g., invalid file type): {ve}", exc_info=True)
             flash(f"Error: {ve}", "error")
             return redirect(request.url)
        except RuntimeError as re:
            # Catch errors raised by generate_cfg_web (including from _generate_and_visualize_cfg)
            app_logger.error(f"Runtime error during CFG generation: {re}", exc_info=True)
            flash(f"Error generating CFG: {re}. Check server logs for details.", "error")
            # Render the error page directly for critical generation errors
            return render_template('error.html', error_message=f"Failed to generate CFG: {re}"), 500
        except Exception as e:
            # Catch any other unexpected errors
            app_logger.error(f"An unexpected error occurred: {e}", exc_info=True)
            flash("An unexpected internal error occurred. Please try again.", "error")
            return render_template('error.html', error_message="An unexpected internal server error occurred."), 500
        finally:
            # Clean up the temporary *input* directory
            if input_temp_dir and os.path.exists(input_temp_dir):
                try:
                    shutil.rmtree(input_temp_dir)
                    app_logger.info(f"Cleaned up input temp directory: {input_temp_dir}")
                except Exception as cleanup_e:
                    app_logger.error(f"Error cleaning up input temp directory '{input_temp_dir}': {cleanup_e}")
            # Output dir cleanup happens within generate_cfg_web on error

    # GET request: just show the upload form
    return render_template('upload.html')

@app.route('/result/<image_dir>/<image_name>')
def show_result(image_dir, image_name):
    """Displays the generated CFG image."""
    app_logger.info(f"Showing result page for image {image_name} from dir {image_dir}")
    return render_template('result.html', image_dir=image_dir, image_name=image_name)

@app.route('/temp/<path:image_dir>/<path:filename>')
def serve_temp_file(image_dir, filename):
    """Serves generated CFG images from their specific temporary directory."""
    directory = os.path.join(tempfile.gettempdir(), image_dir)
    app_logger.info(f"Serving file '{filename}' from directory '{directory}'")
    if not os.path.isdir(directory):
        app_logger.error(f"Temporary directory not found: {directory}")
        return "Image not found or expired (directory missing).", 404
    if not os.path.isfile(os.path.join(directory, filename)):
         app_logger.error(f"Image file not found in directory: {os.path.join(directory, filename)}")
         return "Image not found or expired (file missing).", 404

    # Add cache control headers to suggest browser re-validates
    response = send_from_directory(directory, filename)
    response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '0'
    return response


@app.route('/health')
def health_check():
    return "OK", 200

# --- Error Handlers ---
@app.errorhandler(404)
def page_not_found(e):
    app_logger.warning(f"404 Not Found for URL: {request.url}")
    return render_template('error.html', error_message=f"Page Not Found (404): {request.path}"), 404

@app.errorhandler(500)
def internal_server_error(e):
    # Log the original exception if it's available
    original_exception = getattr(e, 'original_exception', None)
    app_logger.error(f"500 Internal Server Error: {e}", exc_info=original_exception or True)
    # Display a generic message to the user but pass the specific error from generate_cfg_web if it caused this
    error_msg = "Internal Server Error (500). Please contact support if the issue persists."
    if isinstance(original_exception, RuntimeError) and "Failed to generate CFG" in str(original_exception):
         error_msg = str(original_exception) # Show the specific CFG generation error
    return render_template('error.html', error_message=error_msg), 500

@app.errorhandler(413)
def request_entity_too_large(e):
    app_logger.warning(f"File upload rejected (too large): {e}")
    flash(f"File is too large. Maximum size is {app.config['MAX_CONTENT_LENGTH'] // 1024 // 1024}MB.", "error")
    return redirect(url_for('upload_file'))

# --- Main Guard ---
if __name__ == '__main__':
    # Use environment variable for debug mode, default to False
    is_debug = os.environ.get('FLASK_DEBUG', 'False').lower() in ('true', '1', 't')
    app.run(debug=is_debug, host='0.0.0.0', port=int(os.environ.get('PORT', 8080)))
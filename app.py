from flask import Flask, request, render_template, send_from_directory, redirect, url_for, flash
import os
import tempfile
# Removed: from py2cfg import CFGBuilder # Now handled in cfg_generator
from flask_sqlalchemy import SQLAlchemy
import shutil
import logging
from cfg_generator import generate_cfg_web # Import the function

# --- Basic Logging Setup ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# --- Graphviz Path Check ---
logging.info("🚀 Checking dot path at startup...")
dot_path = shutil.which("dot")
logging.info(f"System PATH: {os.environ.get('PATH')}")
logging.info(f"shutil.which('dot') found: {dot_path}")

# Ensure Graphviz's dot is in PATH (Render typically installs it in /usr/bin or /usr/local/bin)
# Adding common paths just in case `shutil.which` fails in some environments
if not dot_path and "/usr/bin" not in os.environ["PATH"]:
    os.environ["PATH"] += os.pathsep + "/usr/bin"
    logging.info("Added /usr/bin to PATH")
if not dot_path and "/usr/local/bin" not in os.environ["PATH"]:
     os.environ["PATH"] += os.pathsep + "/usr/local/bin"
     logging.info("Added /usr/local/bin to PATH")

# Verify again after potential modification
dot_path_after = shutil.which("dot")
logging.info(f"Dot path after potential PATH update: {dot_path_after}")
if not dot_path_after:
    logging.warning("Graphviz 'dot' command not found in PATH. CFG generation will likely fail.")

# --- Flask App Setup ---
app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'dev_secret_key_change_me') # Use a more secure default locally if needed
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', 'sqlite:///site.db') # DATABASE_URL from Render
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['MAX_CONTENT_LENGTH'] = 5 * 1024 * 1024 # Increased limit slightly to 5MB

db = SQLAlchemy(app)

# --- Database Model ---
# PROBLEM: Storing temporary paths in the DB is unreliable. Temporary files get deleted.
# SOLUTION: Remove the Upload model or redesign to store CFG persistently (e.g., cloud storage).
# For now, we'll comment out the DB interaction for simplicity, making the /uploads route non-functional.
# If you need history, implement persistent storage (e.g., Render Disks or external blob storage).

# class Upload(db.Model):
#     id = db.Column(db.Integer, primary_key=True)
#     filename = db.Column(db.String(100), nullable=False)
#     # cfg_path = db.Column(db.String(200), nullable=False) # Storing temp path is bad

# with app.app_context():
#     # db.create_all() # Only create tables if the model is defined and used
#     pass # No DB setup needed if model is commented out

# Removed local generate_cfg_web function, using imported one now

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

        # Save the uploaded file temporarily to pass its path to the generator
        input_temp_dir = None
        output_temp_dir = None # To store the path of the output directory for cleanup
        try:
            input_temp_dir = tempfile.mkdtemp()
            input_path = os.path.join(input_temp_dir, file.filename)
            file.save(input_path)
            logging.info(f"Uploaded file saved temporarily to: {input_path}")

            # Generate CFG image using the imported function
            output_filename = 'cfg.png' # Or generate a unique name if needed
            # generate_cfg_web returns the full path to the generated image in its own temp dir
            cfg_image_path = generate_cfg_web(input_path, output_filename, format='png')
            output_temp_dir = os.path.dirname(cfg_image_path) # Get the directory containing the image

            # --- Database Interaction Removed ---
            # new_upload = Upload(filename=file.filename, cfg_path=cfg_image_path) # Don't save temp path
            # db.session.add(new_upload)
            # db.session.commit()
            # --- ---

            # Pass the *basename* of the image and its *directory* to the template/serving route
            image_name = os.path.basename(cfg_image_path)
            image_dir = os.path.basename(output_temp_dir) # Get the unique temp dir name

            # Redirect to a route that shows the result, passing necessary info
            return redirect(url_for('show_result', image_dir=image_dir, image_name=image_name))

        except FileNotFoundError as fnf:
             logging.error(f"File not found error during upload/processing: {fnf}", exc_info=True)
             flash(f"Error: {fnf}", "error")
             return redirect(request.url) # Go back to upload page on error
        except ValueError as ve:
             logging.error(f"Value error (e.g., invalid file type): {ve}", exc_info=True)
             flash(f"Error: {ve}", "error")
             return redirect(request.url)
        except RuntimeError as re:
            logging.error(f"Runtime error during CFG generation: {re}", exc_info=True)
            flash(f"Error generating CFG: {re}. Check server logs for details.", "error")
             # Maybe render an error page instead of flashing and redirecting
            return render_template('error.html', error_message=f"Failed to generate CFG: {re}"), 500
        except Exception as e:
            logging.error(f"An unexpected error occurred: {e}", exc_info=True)
            flash("An unexpected internal error occurred. Please try again.", "error")
            # Generic error page for unexpected issues
            return render_template('error.html', error_message="An unexpected internal error occurred."), 500
        finally:
            # Clean up the temporary *input* directory
            if input_temp_dir and os.path.exists(input_temp_dir):
                try:
                    shutil.rmtree(input_temp_dir)
                    logging.info(f"Cleaned up input temp directory: {input_temp_dir}")
                except Exception as cleanup_e:
                    logging.error(f"Error cleaning up input temp directory '{input_temp_dir}': {cleanup_e}")
            # Note: The temporary *output* directory (containing the image)
            # needs to persist until the image is served by serve_temp_file.
            # We need a strategy to clean it up *after* it's viewed, which is tricky.
            # Operating systems usually handle temp file cleanup eventually.

    # GET request: just show the upload form
    return render_template('upload.html')

@app.route('/result/<image_dir>/<image_name>')
def show_result(image_dir, image_name):
    """Displays the generated CFG image."""
    # This route now receives the directory and filename
    return render_template('result.html', image_dir=image_dir, image_name=image_name)

@app.route('/temp/<path:image_dir>/<path:filename>')
def serve_temp_file(image_dir, filename):
    """Serves generated CFG images from their specific temporary directory."""
    # Construct the directory path using the system's temp base + the unique dir name
    directory = os.path.join(tempfile.gettempdir(), image_dir)
    logging.info(f"Serving file '{filename}' from directory '{directory}'")
    # Check if dir/file exists for robustness
    if not os.path.isdir(directory):
        logging.error(f"Temporary directory not found: {directory}")
        return "Image not found or expired (directory missing).", 404
    if not os.path.isfile(os.path.join(directory, filename)):
         logging.error(f"Image file not found in directory: {os.path.join(directory, filename)}")
         return "Image not found or expired (file missing).", 404

    # Serve the file
    # Consider adding cleanup logic here or via a background task if temp files accumulate excessively.
    return send_from_directory(directory, filename)

# Removed /uploads route as it relied on the unreliable DB paths
# @app.route('/uploads')
# def list_uploads():
#     # uploads = Upload.query.order_by(Upload.id.desc()).all() # Relied on Upload model
#     # return render_template('uploads.html', uploads=uploads)
#     flash("Upload history is currently disabled.", "info")
#     return redirect(url_for('upload_file'))


@app.route('/health')
def health_check():
    # Could add a DB check here if DB is actively used:
    # try:
    #     db.session.execute('SELECT 1')
    #     return "OK", 200
    # except Exception as e:
    #     logging.error(f"Health check failed: DB connection error - {e}")
    #     return "DB Error", 500
    return "OK", 200 # Basic health check

@app.errorhandler(404)
def page_not_found(e):
    logging.warning(f"404 Not Found for URL: {request.url}")
    return render_template('error.html', error_message=f"Page Not Found (404): {request.path}"), 404

@app.errorhandler(500)
def internal_server_error(e):
    logging.error(f"500 Internal Server Error: {e}", exc_info=True) # Log the exception details
    return render_template('error.html', error_message="Internal Server Error (500). Please contact support if the issue persists."), 500

# Add error handler for file too large
@app.errorhandler(413)
def request_entity_too_large(e):
    logging.warning(f"File upload rejected (too large): {e}")
    flash(f"File is too large. Maximum size is {app.config['MAX_CONTENT_LENGTH'] // 1024 // 1024}MB.", "error")
    return redirect(url_for('upload_file'))


if __name__ == '__main__':
    # Set debug=False for production, True for local development ONLY
    # The Gunicorn command in Dockerfile/Procfile will run the app in production.
    app.run(debug=os.environ.get('FLASK_DEBUG', 'False').lower() == 'true', host='0.0.0.0', port=8080) # Use port 8080 for local dev if 8000 is standard prod
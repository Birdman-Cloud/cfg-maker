from flask import Flask, request, render_template, send_from_directory, redirect, url_for, flash
import os
import tempfile
from py2cfg import CFGBuilder
from flask_sqlalchemy import SQLAlchemy
import shutil, os
print("🚀 Checking dot path at startup...")
print("PATH =", os.environ.get("PATH"))
print("dot found at:", shutil.which("dot"))

# Ensure Graphviz's dot is in PATH (Render typically installs it in /usr/bin or /usr/local/bin)
os.environ["PATH"] += os.pathsep + "/usr/bin" + os.pathsep + "/usr/local/bin"

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'dev_secret_key')
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', 'sqlite:///site.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
# Limit file uploads to 2MB (optional)
app.config['MAX_CONTENT_LENGTH'] = 2 * 1024 * 1024

db = SQLAlchemy(app)

# Define database model for uploads
class Upload(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    filename = db.Column(db.String(100), nullable=False)
    cfg_path = db.Column(db.String(200), nullable=False)

with app.app_context():
    db.create_all()

def generate_cfg_web(input_file, output_file, format='png'):
    """
    Generate a control flow graph (CFG) from a Python file and save it as an image.
    """
    if not input_file.endswith('.py'):
        raise ValueError("Input must be a Python file (.py).")
    output_dir = tempfile.mkdtemp()
    output_path = os.path.join(output_dir, output_file)
    try:
        cfg = CFGBuilder().build_from_file('cfg', input_file)
        if not cfg:
            raise RuntimeError("Generated CFG is empty.")
        cfg.build_visual(output_path, format)
        return output_path
    except Exception as e:
        raise RuntimeError(f"Failed to generate CFG: {e}")

@app.route('/', methods=['GET', 'POST'])
def upload_file():
    if request.method == 'POST':
        # Ensure file is provided
        if 'file' not in request.files:
            flash("No file uploaded", "error")
            return redirect(request.url)
        file = request.files['file']
        if file.filename == '' or not file.filename.endswith('.py'):
            flash("Please upload a valid Python (.py) file", "error")
            return redirect(request.url)
        
        # Save the uploaded file temporarily
        temp_dir = tempfile.mkdtemp()
        input_path = os.path.join(temp_dir, file.filename)
        file.save(input_path)

        # Generate CFG image
        output_file = 'cfg.png'
        try:
            cfg_path = generate_cfg_web(input_path, output_file)
            # Save upload details in the database
            new_upload = Upload(filename=file.filename, cfg_path=cfg_path)
            db.session.add(new_upload)
            db.session.commit()
            # Save basename only to serve it later
            image_name = os.path.basename(cfg_path)
            return render_template('result.html', image_file=image_name)
        except Exception as e:
            flash(f"Error generating CFG: {e}", "error")
            return render_template('error.html', error_message=str(e)), 500
    return render_template('upload.html')

@app.route('/temp/<path:filename>')
def serve_temp_file(filename):
    # Serve generated CFG images from the temporary directory
    return send_from_directory(tempfile.gettempdir(), filename)

@app.route('/uploads')
def list_uploads():
    # Display a history of uploads
    uploads = Upload.query.order_by(Upload.id.desc()).all()
    return render_template('uploads.html', uploads=uploads)

# Health check endpoint for cloud monitoring
@app.route('/health')
def health_check():
    return "OK", 200

# Custom error handlers
@app.errorhandler(404)
def page_not_found(e):
    return render_template('error.html', error_message="Page Not Found (404)"), 404

@app.errorhandler(500)
def internal_server_error(e):
    return render_template('error.html', error_message="Internal Server Error (500)"), 500

if __name__ == '__main__':
    app.run(debug=True)

from flask import Flask, request, render_template, send_from_directory
from flask_sqlalchemy import SQLAlchemy
import os
import tempfile
from py2cfg import CFGBuilder

# Initialize Flask app
app = Flask(__name__)

# Configure database (use Heroku's DATABASE_URL or fallback to SQLite for local testing)
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', 'sqlite:///site.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# Define database model
class Upload(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    filename = db.Column(db.String(100), nullable=False)
    cfg_path = db.Column(db.String(200), nullable=False)

# Create database tables
with app.app_context():
    db.create_all()

# CFG generation function (from Step 3)
def generate_cfg_web(input_file, output_file, format='png'):
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

# Route for file upload and CFG generation
@app.route('/', methods=['GET', 'POST'])
def upload_file():
    if request.method == 'POST':
        # Check if a file was uploaded
        if 'file' not in request.files:
            return "No file uploaded", 400
        file = request.files['file']
        if file.filename == '' or not file.filename.endswith('.py'):
            return "Please upload a valid Python (.py) file", 400

        # Save the uploaded file temporarily
        temp_dir = tempfile.mkdtemp()
        input_path = os.path.join(temp_dir, file.filename)
        file.save(input_path)

        # Generate CFG
        output_file = 'cfg.png'
        try:
            cfg_path = generate_cfg_web(input_path, output_file)
            # Store upload details in the database
            new_upload = Upload(filename=file.filename, cfg_path=cfg_path)
            db.session.add(new_upload)
            db.session.commit()
            # Render the result page with the CFG image
            return render_template('result.html', image_file=os.path.basename(cfg_path))
        except Exception as e:
            return f"Error: {e}", 500

    # On GET request, show the upload form
    return render_template('upload.html')

# Route to serve temporary files (CFG images)
@app.route('/temp/<path:filename>')
def serve_temp_file(filename):
    return send_from_directory(tempfile.gettempdir(), filename)

if __name__ == '__main__':
    app.run(debug=True)
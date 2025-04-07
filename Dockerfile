# Use an official Python runtime as a parent image
# Using slim-buster for a smaller image size
FROM python:3.11-slim-buster

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE 1  # Prevents python from writing pyc files
ENV PYTHONUNBUFFERED 1      # Prevents python from buffering stdout/stderr

# Set the working directory in the container
WORKDIR /app

# Install system dependencies required by graphviz and potentially other libraries
# Using --no-install-recommends reduces image size
RUN apt-get update \
    && apt-get install -y --no-install-recommends graphviz gcc \
    # Clean up APT cache to reduce image size
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
# Copy only requirements first to leverage Docker cache
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application code into the container
COPY . .

# Expose the port the app runs on (Gunicorn default is often 8000, but Render expects 80 or others, let's use 8080)
# Note: Render maps its internal port to 80/443 externally. Gunicorn needs to bind to the specified port.
EXPOSE 8080

# Define the command to run the application using Gunicorn
# Bind to 0.0.0.0 to accept connections from outside the container
# Use the PORT environment variable Render injects, or default to 8080
# Ensure app:app matches your Flask app entry point (filename:variable)
CMD ["gunicorn", "app:app", "--bind", "0.0.0.0:8080"]
# Dockerfile

FROM python:3.11-slim

# Install dependencies including Graphviz
RUN apt-get update && \
    apt-get install -y graphviz gcc g++ && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

# Set work directory
WORKDIR /app

# Copy files
COPY . .

# Install Python dependencies
RUN pip install --upgrade pip && pip install -r requirements.txt

# Set environment variable to ensure Graphviz's `dot` is in PATH
ENV PATH="/usr/bin:/usr/local/bin:$PATH"

# For debugging: print dot path
RUN which dot

# Expose port
EXPOSE 8000

# Start the app
CMD ["gunicorn", "app:app", "--bind", "0.0.0.0:8000"]
